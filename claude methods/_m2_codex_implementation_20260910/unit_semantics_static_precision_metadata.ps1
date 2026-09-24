param([string]$AssemblyPath='D:\同花顺软件\同花顺远航版\bin\Hevo.Api.Quotes.dll')
# Pure PE metadata and constant-data reads. Never loads or invokes the target DLL.
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $AssemblyPath).Path
$stream=[IO.File]::OpenRead($resolved)
$pe=[System.Reflection.PortableExecutable.PEReader]::new($stream)
try {
  $md=[System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
  'ASSEMBLY '+$resolved
  'SHA256 '+(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
  foreach($token in @(0x04002255,0x04002063,0x04002053,0x04002054,0x04002055,0x04002056)) {
    $handle=[System.Reflection.Metadata.Ecma335.MetadataTokens]::FieldDefinitionHandle($token -band 0xFFFFFF)
    $field=$md.GetFieldDefinition($handle)
    $type=$md.GetTypeDefinition($field.GetDeclaringType())
    'FIELD '+('0x{0:X8}' -f $token)+' '+$md.GetString($type.Namespace)+'.'+$md.GetString($type.Name)+'::'+$md.GetString($field.Name)+' SIGNATURE '+[Convert]::ToHexString($md.GetBlobBytes($field.Signature))+' RVA '+$field.GetRelativeVirtualAddress()
    if($token -eq 0x04002255) {
      [byte[]]$bytes=$pe.GetSectionData([int]$field.GetRelativeVirtualAddress()).GetContent(0,32)
      'CONSTANT32_HEX '+[Convert]::ToHexString($bytes)
      $values=0..7 | ForEach-Object {[BitConverter]::ToInt32($bytes,$_ * 4)}
      'INT32_ARRAY '+($values -join ',')
    }
  }
  foreach($token in @(0x06001A93,0x06001A87,0x0600035F)) {
    $handle=[System.Reflection.Metadata.Ecma335.MetadataTokens]::MethodDefinitionHandle($token -band 0xFFFFFF)
    $method=$md.GetMethodDefinition($handle)
    $type=$md.GetTypeDefinition($method.GetDeclaringType())
    'METHOD '+('0x{0:X8}' -f $token)+' '+$md.GetString($type.Namespace)+'.'+$md.GetString($type.Name)+'::'+$md.GetString($method.Name)+' SIGNATURE '+[Convert]::ToHexString($md.GetBlobBytes($method.Signature))
  }
} finally {$pe.Dispose();$stream.Dispose()}
