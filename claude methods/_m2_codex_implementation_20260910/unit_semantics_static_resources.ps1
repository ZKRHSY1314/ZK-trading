param([Parameter(Mandatory=$true)][string]$AssemblyPath,
      [Parameter(Mandatory=$true)][string]$OutputDirectory)
# Pure PE/metadata resource read. Never load or invoke the target assembly.
$ErrorActionPreference = 'Stop'
$assembly = (Resolve-Path -LiteralPath $AssemblyPath).Path
$out = (Resolve-Path -LiteralPath $OutputDirectory).Path
$stream = [System.IO.File]::OpenRead($assembly)
$pe = [System.Reflection.PortableExecutable.PEReader]::new($stream)
try {
    $md = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
    'ASSEMBLY ' + $assembly
    'SHA256 ' + (Get-FileHash -LiteralPath $assembly -Algorithm SHA256).Hash
    $resourceRva = $pe.PEHeaders.CorHeader.ResourcesDirectory.RelativeVirtualAddress
    foreach ($handle in $md.ManifestResources) {
        $resource = $md.GetManifestResource($handle)
        $name = $md.GetString($resource.Name)
        if ($name -notmatch '(QuoteFieldData|MarketInfo|MarketData|Market).*xml$') {continue}
        if (-not $resource.Implementation.IsNil) {throw 'external resource not read'}
        'RESOURCE_OFFSET ' + $name + ' RVA ' + $resourceRva + ' OFFSET ' + $resource.Offset + ' SIZE ' + $pe.PEHeaders.CorHeader.ResourcesDirectory.Size
        $block = $pe.GetSectionData([int]($resourceRva + $resource.Offset))
        'BLOCK_LENGTH ' + $block.Length
        $prefix = [byte[]]@($block.GetContent(0,4))
        $length = [BitConverter]::ToInt32($prefix,0)
        if ($length -lt 0 -or $length -gt 2097152) {throw 'resource size outside read bound'}
        $bytes = [byte[]]@($block.GetContent(4,$length))
        $destination = Join-Path $out ('unit_semantics_static_resource_' + $name)
        $writer = [System.IO.File]::Open($destination,[System.IO.FileMode]::CreateNew)
        try {$writer.Write($bytes,0,$bytes.Length)} finally {$writer.Dispose()}
        'RESOURCE ' + $name + ' LENGTH ' + $length + ' SHA256 ' + (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    }
} finally {$pe.Dispose();$stream.Dispose()}
