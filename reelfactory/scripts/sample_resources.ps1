# Samples system CPU % and the RAM of the factory's processes every 2 s until the file STOP exists.
param([string]$Out = "resources.csv", [string]$Stop = "resources.stop")
"t,cpu_total_pct,factory_ram_mb,node_mb,python_mb,ffmpeg_mb,chrome_mb" | Out-File $Out -Encoding ascii
while (-not (Test-Path $Stop)) {
  $cpu = [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue, 1)
  $g = Get-Process -ErrorAction SilentlyContinue | Group-Object ProcessName -AsHashTable -AsString
  function mb($n) { if ($g.ContainsKey($n)) { [math]::Round(($g[$n] | Measure-Object WorkingSet64 -Sum).Sum / 1MB) } else { 0 } }
  $n = mb 'node'; $p = mb 'python'; $f = mb 'ffmpeg'; $c = 0; if ($g.ContainsKey('chrome')) { $c = [math]::Round((($g['chrome'] | Where-Object { $_.Path -like '*puppeteer*' }) | Measure-Object WorkingSet64 -Sum).Sum / 1MB) }
  "{0},{1},{2},{3},{4},{5},{6}" -f (Get-Date -Format "HH:mm:ss"), $cpu, ($n + $p + $f + $c), $n, $p, $f, $c | Out-File $Out -Append -Encoding ascii
  Start-Sleep -Seconds 1
}
