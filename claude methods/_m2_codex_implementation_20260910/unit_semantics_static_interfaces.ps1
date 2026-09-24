param([Parameter(Mandatory=$true)][string]$AssemblyPath,
      [string]$InterfacePattern='ICandleParser|ICandleRequestDispatcher|ITimeTableReplyData|ICandleReplyData')
# Metadata-only interface implementation inventory; no target DLL load.
$ErrorActionPreference='Stop'
$source=(Resolve-Path -LiteralPath $AssemblyPath).Path
$stream=[IO.File]::OpenRead($source)
$pe=[System.Reflection.PortableExecutable.PEReader]::new($stream)
try {
  $md=[System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
  'ASSEMBLY '+$source
  'SHA256 '+(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
  foreach($handle in $md.TypeDefinitions) {
    $type=$md.GetTypeDefinition($handle)
    foreach($ih in $type.GetInterfaceImplementations()) {
      $item=$md.GetInterfaceImplementation($ih).Interface
      if($item.Kind.ToString() -eq 'TypeReference') {
        $tr=$md.GetTypeReference([System.Reflection.Metadata.TypeReferenceHandle]$item)
        $iname=$md.GetString($tr.Namespace)+'.'+$md.GetString($tr.Name)
      } elseif($item.Kind.ToString() -eq 'TypeDefinition') {
        $tr=$md.GetTypeDefinition([System.Reflection.Metadata.TypeDefinitionHandle]$item)
        $iname=$md.GetString($tr.Namespace)+'.'+$md.GetString($tr.Name)
      } else {continue}
      if($iname -notmatch $InterfacePattern){continue}
      'TYPE '+$md.GetString($type.Namespace)+'.'+$md.GetString($type.Name)+' INTERFACE '+$iname
      foreach($mh in $type.GetMethods()) {
        $m=$md.GetMethodDefinition($mh)
        '  METHOD '+$md.GetString($m.Name)+' TOKEN '+('0x{0:X8}' -f [System.Reflection.Metadata.Ecma335.MetadataTokens]::GetToken([System.Reflection.Metadata.EntityHandle]$mh))
      }
    }
  }
} finally {$pe.Dispose();$stream.Dispose()}
