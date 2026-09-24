param(
    [Parameter(Mandatory = $true)][string]$AssemblyPath,
    [string]$TypePattern = 'HevoQuoteCandleService',
    [string]$MethodPattern = '.',
    [int[]]$MethodTokens = @(),
    [switch]$ListOnly
)

# Static PE/ECMA-335 inspection only. Target assemblies are never loaded.
# No network, plugin calls, runtime config discovery, or target method invocation.
$ErrorActionPreference = 'Stop'
$resolvedPath = (Resolve-Path -LiteralPath $AssemblyPath).Path
$stream = [System.IO.File]::OpenRead($resolvedPath)
$pe = $null
try {
    $pe = [System.Reflection.PortableExecutable.PEReader]::new($stream)
    $md = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
    $module = $md.GetModuleDefinition()
    'ASSEMBLY ' + $resolvedPath
    'SHA256 ' + (Get-FileHash -LiteralPath $resolvedPath -Algorithm SHA256).Hash
    'MVID ' + $md.GetGuid($module.Mvid)
    'FILTER type=' + $TypePattern + ' method=' + $MethodPattern
    if ($MethodTokens.Count) { 'FILTER tokens=' + (($MethodTokens | ForEach-Object { '0x{0:X8}' -f $_ }) -join ',') }

    function Get-TypeName($handle) {
        $handle = [System.Reflection.Metadata.EntityHandle]$handle
        if ($handle.IsNil) { return '<nil>' }
        $kind = $handle.Kind.ToString()
        if ($kind -eq 'TypeDefinition') {
            $item = $md.GetTypeDefinition([System.Reflection.Metadata.TypeDefinitionHandle]$handle)
            $name = $md.GetString($item.Name)
            $parent = $item.GetDeclaringType()
            if (-not $parent.IsNil) { return (Get-TypeName $parent) + '+' + $name }
            $ns = $md.GetString($item.Namespace)
            if ($ns) { return $ns + '.' + $name }
            return $name
        }
        if ($kind -eq 'TypeReference') {
            $item = $md.GetTypeReference([System.Reflection.Metadata.TypeReferenceHandle]$handle)
            return $md.GetString($item.Namespace) + '.' + $md.GetString($item.Name)
        }
        if ($kind -eq 'TypeSpecification') {
            $item = $md.GetTypeSpecification([System.Reflection.Metadata.TypeSpecificationHandle]$handle)
            return 'TypeSpec[' + [Convert]::ToHexString($md.GetBlobBytes($item.Signature)) + ']'
        }
        return $kind
    }

    function Get-TokenText([int]$token) {
        if (($token -band -16777216) -eq 1879048192) {
            $value = $md.GetUserString([System.Reflection.Metadata.Ecma335.MetadataTokens]::UserStringHandle($token -band 16777215))
            return '"' + ($value -replace "`r", '\r' -replace "`n", '\n') + '"'
        }
        $handle = [System.Reflection.Metadata.Ecma335.MetadataTokens]::EntityHandle($token)
        switch ($handle.Kind.ToString()) {
            'MethodDefinition' {
                $item = $md.GetMethodDefinition([System.Reflection.Metadata.MethodDefinitionHandle]$handle)
                return (Get-TypeName $item.GetDeclaringType()) + '::' + $md.GetString($item.Name)
            }
            'FieldDefinition' {
                $item = $md.GetFieldDefinition([System.Reflection.Metadata.FieldDefinitionHandle]$handle)
                return (Get-TypeName $item.GetDeclaringType()) + '::' + $md.GetString($item.Name)
            }
            'MemberReference' {
                $item = $md.GetMemberReference([System.Reflection.Metadata.MemberReferenceHandle]$handle)
                return (Get-TypeName $item.Parent) + '::' + $md.GetString($item.Name)
            }
            'MethodSpecification' {
                $item = $md.GetMethodSpecification([System.Reflection.Metadata.MethodSpecificationHandle]$handle)
                return (Get-TokenText ([System.Reflection.Metadata.Ecma335.MetadataTokens]::GetToken($item.Method))) + '<' + [Convert]::ToHexString($md.GetBlobBytes($item.Signature)) + '>'
            }
            { $_ -in 'TypeDefinition', 'TypeReference', 'TypeSpecification' } { return Get-TypeName $handle }
            default { return $handle.Kind.ToString() }
        }
    }

    $opcodes = @{}
    foreach ($field in [System.Reflection.Emit.OpCodes].GetFields([System.Reflection.BindingFlags]'Public,Static')) {
        $opcode = $field.GetValue($null)
        $opcodes[[int]$opcode.Value -band 65535] = $opcode
    }

    foreach ($typeHandle in $md.TypeDefinitions) {
        $typeName = Get-TypeName $typeHandle
        if ($typeName -notmatch $TypePattern) { continue }
        $type = $md.GetTypeDefinition($typeHandle)
        if ($ListOnly) {
            'TYPE ' + $typeName + ' base=' + (Get-TypeName $type.BaseType)
            foreach ($fieldHandle in $type.GetFields()) {
                $field = $md.GetFieldDefinition($fieldHandle)
                $constantHandle = $field.GetDefaultValue()
                if (-not $constantHandle.IsNil) {
                    $constant = $md.GetConstant($constantHandle)
                    $constantBytes = $md.GetBlobBytes($constant.Value)
                    $constantValue = if ($constant.TypeCode.ToString() -eq 'Int32') { [BitConverter]::ToInt32($constantBytes, 0) } else { [Convert]::ToHexString($constantBytes) }
                    '  FIELD {0} token=0x{1:X8} constant={2} type={3}' -f $md.GetString($field.Name), ([System.Reflection.Metadata.Ecma335.MetadataTokens]::GetToken([System.Reflection.Metadata.EntityHandle]$fieldHandle)), $constantValue, $constant.TypeCode
                }
            }
            foreach ($propertyHandle in $type.GetProperties()) {
                $property = $md.GetPropertyDefinition($propertyHandle)
                '  PROPERTY ' + $md.GetString($property.Name)
            }
        }
        foreach ($methodHandle in $type.GetMethods()) {
            $method = $md.GetMethodDefinition($methodHandle)
            $methodName = $md.GetString($method.Name)
            if ($methodName -notmatch $MethodPattern) { continue }
            $token = [System.Reflection.Metadata.Ecma335.MetadataTokens]::GetToken([System.Reflection.Metadata.EntityHandle]$methodHandle)
            if ($MethodTokens.Count -and $token -notin $MethodTokens) { continue }
            $parameters = foreach ($parameterHandle in $method.GetParameters()) {
                $parameter = $md.GetParameter($parameterHandle)
                $md.GetString($parameter.Name)
            }
            'METHOD {0}::{1} token=0x{2:X8} RVA=0x{3:X8} params=({4})' -f $typeName, $methodName, $token, $method.RelativeVirtualAddress, ($parameters -join ',')
            if ($ListOnly -or -not $method.RelativeVirtualAddress) { continue }
            $body = [System.Reflection.Metadata.PEReaderExtensions]::GetMethodBody($pe, $method.RelativeVirtualAddress)
            $bytes = $body.GetILBytes()
            $position = 0
            while ($position -lt $bytes.Length) {
                $offset = $position
                $value = [int]$bytes[$position++]
                if ($value -eq 254) { $value = 65024 + [int]$bytes[$position++] }
                $opcode = $opcodes[$value]
                if (-not $opcode) { throw ('Unknown opcode {0:X4} at {1:X4}' -f $value, $offset) }
                $operand = ''
                switch ($opcode.OperandType.ToString()) {
                    'InlineNone' { }
                    'ShortInlineI' { $operand = [int]$bytes[$position++]; if ($operand -gt 127) { $operand -= 256 } }
                    'ShortInlineVar' { $operand = [int]$bytes[$position++] }
                    'InlineVar' { $operand = [BitConverter]::ToUInt16($bytes, $position); $position += 2 }
                    'InlineI' { $operand = [BitConverter]::ToInt32($bytes, $position); $position += 4 }
                    'InlineI8' { $operand = [BitConverter]::ToInt64($bytes, $position); $position += 8 }
                    'ShortInlineR' { $operand = [BitConverter]::ToSingle($bytes, $position); $position += 4 }
                    'InlineR' { $operand = [BitConverter]::ToDouble($bytes, $position); $position += 8 }
                    'ShortInlineBrTarget' {
                        $delta = [int]$bytes[$position++]; if ($delta -gt 127) { $delta -= 256 }
                        $operand = 'IL_{0:X4}' -f ($position + $delta)
                    }
                    'InlineBrTarget' {
                        $delta = [BitConverter]::ToInt32($bytes, $position); $position += 4
                        $operand = 'IL_{0:X4}' -f ($position + $delta)
                    }
                    'InlineSwitch' {
                        $count = [BitConverter]::ToInt32($bytes, $position); $position += 4
                        $base = $position + 4 * $count
                        $destinations = for ($i = 0; $i -lt $count; $i++) {
                            'IL_{0:X4}' -f ($base + [BitConverter]::ToInt32($bytes, $position)); $position += 4
                        }
                        $operand = $destinations -join ','
                    }
                    default {
                        $reference = [BitConverter]::ToInt32($bytes, $position); $position += 4
                        $operand = '0x{0:X8} {1}' -f $reference, (Get-TokenText $reference)
                    }
                }
                '  IL_{0:X4}: {1,-12} {2}' -f $offset, $opcode.Name, $operand
            }
        }
    }
} finally {
    if ($pe) { $pe.Dispose() }
    $stream.Dispose()
}
