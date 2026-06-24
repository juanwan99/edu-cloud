from scripts.yuanqi.lock_map import expand_exclusive, module_paths, module_tables


def test_module_tables_reads_real_modules_yaml_for_grading():
    tables = module_tables("grading")

    assert tables
    assert "grading_results" in tables


def test_module_paths_includes_source_and_existing_grading_tests():
    paths = module_paths("grading")

    assert paths
    assert "src/edu_cloud/modules/grading/**" in paths
    assert any("test_grading" in path for path in paths)


def test_expand_exclusive_db_migration_includes_alembic():
    paths = expand_exclusive("db_migration")

    assert paths
    assert any("alembic" in path for path in paths)
