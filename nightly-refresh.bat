@echo off
rem Nightly wiki refresh, run by Windows Task Scheduler on this PC (the wiki blocks cloud runners).
rem Re-scrapes quests / items / npcs / zones and recipes, checks the result looks sane, and pushes whatever
rem changed to GitHub. The overlays and the Discord bots pull the data from GitHub on their own.
rem If the check fails (a file came back empty or much smaller), nothing is pushed and you get a Discord DM.
setlocal
set LOG=%~dp0nightly-refresh.log
echo ==== %date% %time% ==== >> "%LOG%"

cd /d "%~dp0"
python wiki_quests.py >> "%LOG%" 2>&1 || echo quests scrape failed >> "%LOG%"
python wiki_data.py >> "%LOG%" 2>&1 || echo data scrape failed >> "%LOG%"

cd /d "%~dp0..\mobetta-crafts"
python wiki_recipes.py >> "%LOG%" 2>&1 || echo recipes scrape failed >> "%LOG%"

cd /d "%~dp0"
python refresh_check.py >> "%LOG%" 2>&1 || (echo NOT PUBLISHED: refresh check failed >> "%LOG%" & goto :done)

git add quests.json items.json npcs.json zones.json >> "%LOG%" 2>&1
git diff --cached --quiet || (git -c user.name="wiki-refresh" -c user.email="amyklindley@gmail.com" commit -q -m "Wiki data refresh %date%" && git push -q) >> "%LOG%" 2>&1

cd /d "%~dp0..\mobetta-crafts"
git add recipes.json >> "%LOG%" 2>&1
git diff --cached --quiet || (git -c user.name="wiki-refresh" -c user.email="amyklindley@gmail.com" commit -q -m "Wiki data refresh %date%" && git push -q) >> "%LOG%" 2>&1

:done
echo done >> "%LOG%"
endlocal
