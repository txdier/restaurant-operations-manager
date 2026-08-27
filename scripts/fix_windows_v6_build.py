from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


database = Path("desktop/restaurant_manager/database.py")
replace_once(
    database,
    '            with sqlite3.connect(str(self.path)) as source, sqlite3.connect(str(candidate)) as dest:\n                source.backup(dest)',
    '            with closing(sqlite3.connect(str(self.path))) as source, closing(sqlite3.connect(str(candidate))) as dest:\n                source.backup(dest)',
    "candidate snapshot connections",
)
replace_once(
    database,
    '            with sqlite3.connect(str(candidate), timeout=15) as conn:\n                migrate_database(conn)',
    '            with closing(sqlite3.connect(str(candidate), timeout=15)) as conn:\n                migrate_database(conn)',
    "candidate validation connection",
)
replace_once(
    database,
    '        with sqlite3.connect(str(self.path)) as source, sqlite3.connect(str(target)) as dest:\n            source.backup(dest)',
    '        with closing(sqlite3.connect(str(self.path))) as source, closing(sqlite3.connect(str(target))) as dest:\n            source.backup(dest)',
    "migration backup connections",
)

static_test = Path("desktop/tests/test_static_content.py")
replace_once(
    static_test,
    '    assert \'if(active==="data")return <DataExchange\' in page',
    '    assert \'if(active==="data")return isDesktop()?<DataExchangeV2 toast={setToast}/>:<DataExchange expenses={expenses} toast={setToast}/>\' in page',
    "data exchange v2 assertion",
)

print("Windows v6 build fixes applied")
