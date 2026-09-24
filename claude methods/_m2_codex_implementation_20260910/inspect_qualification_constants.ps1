param([Parameter(Mandatory=$true)][string]$AssemblyPath,
      [string]$TypePattern='QuoteAdjustmentKind|RightStatus|RightArgs|Candle|Price|Volume')
# PE metadata only: no target assembly loading or invocation, no network/config access.
$ErrorActionPreference='Stop'
$p=(Resolve-Path -LiteralPath $AssemblyPath).Path
$s=[IO.File]::OpenRead($p)
$pe=$null
try {
  $pe=[Reflection.PortableExecutable.PEReader]::new($s)
  $md=[Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
  'ASSEMBLY '+$p
  'SHA256 '+(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
  'MVID '+$md.GetGuid($md.GetModuleDefinition().Mvid)
  foreach($h in $md.TypeDefinitions) {
    $t=$md.GetTypeDefinition($h)
    $n=$md.GetString($t.Namespace)+'.'+$md.GetString($t.Name)
    if($n -notmatch $TypePattern) { continue }
    'TYPE '+$n
    foreach($fh in $t.GetFields()) {
      $f=$md.GetFieldDefinition($fh)
      $name=$md.GetString($f.Name)
      $ch=$f.GetDefaultValue()
      $value='<no constant>'
      if(-not $ch.IsNil) {
        $c=$md.GetConstant($ch)
        $r=$md.GetBlobReader($c.Value)
        $value=switch($c.TypeCode.ToString()) {
          'Int32' {$r.ReadInt32()}
          'UInt32' {$r.ReadUInt32()}
          'Int64' {$r.ReadInt64()}
          'Boolean' {$r.ReadBoolean()}
          'String' {$r.ReadUTF16($r.Length)}
          default {'blob='+[Convert]::ToHexString($md.GetBlobBytes($c.Value))}
        }
      }
      'FIELD '+$name+' = '+$value+'; attributes='+$f.Attributes
    }
  }
} finally {if($pe){$pe.Dispose()};$s.Dispose()}
