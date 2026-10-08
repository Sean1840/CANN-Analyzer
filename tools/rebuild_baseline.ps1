# Rebuild catalogs/baseline/sites.sqlite from shallow clones in a temp workspace.
# Clones go to $env:TEMP\cann-analyze-baseline\repos and are deleted at the end.
# Run: pwsh -File tools\rebuild_baseline.ps1 [-KeepClones]
param(
  [switch]$KeepClones,
  [int]$Parallel = 4
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$py = 'C:\Users\w30045765\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$work = Join-Path $env:TEMP 'cann-analyze-baseline'
$clones = Join-Path $work 'repos'
New-Item -ItemType Directory -Force -Path $clones | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Output "[$stamp] work=$work repo=$repo"

# id -> git url (baseline only). Kept in sync with catalogs/repos.json.
$targets = [ordered]@{
  'cann/runtime'  = 'https://gitcode.com/cann/runtime.git'
  'ascend/msprof' = 'https://gitcode.com/Ascend/msprof.git'
  'cann/driver'   = 'https://gitcode.com/cann/driver.git'
  'cann/hccl'     = 'https://gitcode.com/cann/hccl.git'
  'cann/hcomm'    = 'https://gitcode.com/cann/hcomm.git'
  'cann/ops-nn'   = 'https://gitcode.com/cann/ops-nn.git'
  'cann/ops-math' = 'https://gitcode.com/cann/ops-math.git'
  'cann/ops-cv'   = 'https://gitcode.com/cann/ops-cv.git'
}

$jobs = @()
foreach ($id in $targets.Keys) {
  $name = $targets[$id].Split('/')[-1].Replace('.git', '')
  $dest = Join-Path $clones $name
  if (Test-Path (Join-Path $dest '.git')) { Write-Output "[skip] $id already cloned"; continue }
  $jobs += Start-Job -Name $name -ScriptBlock {
    param($url, $dest, $name)
    $log = & git clone --depth 1 --single-branch --quiet $url $dest 2>&1
    [pscustomobject]@{ name = $name; code = $LASTEXITCODE; log = ($log | Out-String).Trim() }
  } -ArgumentList $targets[$id], $dest, $name
  Write-Output "[clone] started $id -> $dest"
}

if ($jobs.Count) {
  $done = $jobs | Wait-Job
  foreach ($job in $done) {
    $out = Receive-Job $job
    Write-Output ("[{0}] exit={1} {2}" -f $out.name, $out.code, $out.log)
    Remove-Job $job
  }
}

# Report what landed.
Get-ChildItem $clones -Directory | ForEach-Object {
  $head = (& git -C $_.FullName rev-parse --short HEAD 2>&1)
  $size = [math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
    Measure-Object Length -Sum).Sum / 1MB, 1)
  Write-Output ("[have] {0,-12} {1} {2} MB" -f $_.Name, $head, $size)
}

# Point the catalog at the temp clones (gitignored file, deleted at the end).
$map = [ordered]@{}
foreach ($id in $targets.Keys) {
  $name = $targets[$id].Split('/')[-1].Replace('.git', '')
  $dest = Join-Path $clones $name
  if (Test-Path (Join-Path $dest '.git')) {
    $map[$id] = ($dest -replace '\\', '/')
  } else {
    Write-Output "[missing] $id - baseline build will report no_local_clone for it"
  }
}
$localFile = Join-Path $repo 'catalogs\repos.local.json'
@{
  schema = 'cann-analyze.repos-local.v1'
  notes  = 'Temporary mapping written by tools/rebuild_baseline.ps1; deleted after the rebuild.'
  local_paths = $map
} | ConvertTo-Json -Depth 4 | Set-Content -Path $localFile -Encoding UTF8
Write-Output "[map] wrote $localFile with $($map.Count) entries"

# Rebuild the shipped baseline (store_source=False, so no machine paths are recorded).
Push-Location $repo
try {
  $env:PYTHONPATH = Join-Path $repo 'tools'
  & $py -m cann_analyze index --baseline -o (Join-Path $work 'baseline-build.json')
  Write-Output "[build] exit=$LASTEXITCODE"
  & $py -m cann_analyze coverage -o (Join-Path $work 'coverage-after.json')
  Write-Output "[coverage] exit=$LASTEXITCODE"
} finally {
  Pop-Location
}

Write-Output "[size] sites.sqlite = $([math]::Round((Get-Item (Join-Path $repo 'catalogs\baseline\sites.sqlite')).Length / 1MB, 1)) MB"

# Clean up: clones, the temporary repo mapping, and the work dir (unless -KeepClones).
Remove-Item $localFile -Force -ErrorAction SilentlyContinue
Write-Output "[clean] removed $localFile"
if (-not $KeepClones) {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
  Write-Output "[clean] removed $work"
} else {
  Write-Output "[keep] clones kept at $work"
}
Write-Output "[done] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
