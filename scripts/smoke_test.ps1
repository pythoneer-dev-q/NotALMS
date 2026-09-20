# smoke test: поднимаем back+front и дергаем эндпоинты
$ErrorActionPreference = 'Continue'
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
$py = (Get-Command python).Source
Start-Process $py -ArgumentList '-m','back.server.main'  -WindowStyle Hidden -RedirectStandardOutput 'back_smoke.log'  -RedirectStandardError 'back_smoke.err'
Start-Process $py -ArgumentList '-m','front.server.main' -WindowStyle Hidden -RedirectStandardOutput 'front_smoke.log' -RedirectStandardError 'front_smoke.err'
Start-Sleep -Seconds 6

$login = 'smoke_' + (Get-Random -Maximum 99999)
$body = '{"user_login":"' + $login + '","user_password":"pw123456","about_user":null}'
$tok = $null
try {
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:8004/v1/register -ContentType 'application/json' -Body $body -TimeoutSec 5
    $j = $r.Content | ConvertFrom-Json
    $tok = $j.JWTSession
    "REGISTER=200 uid=$($j.user_uid)"
} catch { "REGISTER_STATUS=$($_.Exception.Response.StatusCode.value__)"; $tok = $null }

if ($tok) {
    $h = @{ Authorization = "Bearer $tok" }
    foreach($ep in 'me','me/progress','rating/leaderboard','search_user'){
        try { $x = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8004/v1/$ep" -Headers $h -TimeoutSec 5; "${ep}=$($x.StatusCode)" }
        catch { "${ep}_STATUS=$($_.Exception.Response.StatusCode.value__)" }
    }
    # тема: валидная сохраняется, мусорная отбивается
    try { $t1 = Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:8004/v1/me/theme -Headers $h -ContentType 'application/json' -Body '{"name":"emerald"}' -TimeoutSec 5; "THEME_SET=$($t1.StatusCode):$($t1.Content)" } catch { "THEME_SET_FAIL" }
    try { Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:8004/v1/me/theme -Headers $h -ContentType 'application/json' -Body '{"name":"hack"}' -TimeoutSec 5 | Out-Null; "THEME_BAD=200 (плохо)" } catch { "THEME_BAD_STATUS=$($_.Exception.Response.StatusCode.value__) (400 = ok)" }
    try { $lb = (Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8004/v1/rating/leaderboard -Headers $h -TimeoutSec 5).Content; "LEADERBOARD=$lb" } catch { "LB_FAIL" }
}

try { $ck = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8004/v1/check-login/$login" -TimeoutSec 5; "CHECKLOGIN=$($ck.StatusCode)" } catch { "CHECKLOGIN_FAIL" }
try { $fv = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8005/favicon.ico -TimeoutSec 5; "FAVICON=$($fv.StatusCode) len=$($fv.RawContentLength)" } catch { "FAVICON_FAIL" }
try { $st = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8004/v1/stats/public -TimeoutSec 5; "STATS=$($st.StatusCode):$($st.Content)" } catch { "STATS_FAIL" }
try { $th = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8004/v1/themes -TimeoutSec 5; "THEMES=$($th.Content)" } catch { "THEMES_FAIL" }
try { $tg = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8005/tg/123456 -TimeoutSec 5; "TGROUTE=$($tg.StatusCode)" } catch { "TGROUTE_FAIL" }
try { Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:8004/v1/login/telegram -ContentType 'application/json' -Body '{"code":"000000"}' -TimeoutSec 5 | Out-Null; "TGLOGIN=200" } catch { "TGLOGIN_STATUS=$($_.Exception.Response.StatusCode.value__) (403 = ok)" }
# админка: без секрета createCourse должен отдавать 403
try { Invoke-WebRequest -UseBasicParsing -Method Post -Uri http://127.0.0.1:8004/v1/createCourse -ContentType 'application/json' -Body '{"id":"smoke","title":"t","description":"d","cover":"c","difficulty":"easy","tags":[],"lessons":[],"granted_to":["all"]}' -TimeoutSec 5 | Out-Null; "ADMIN_GUARD=200 (плохо)" } catch { "ADMIN_GUARD_STATUS=$($_.Exception.Response.StatusCode.value__) (403 = ok)" }

Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
"SMOKE_DONE"
