from minio_migration import migration_paths


def test_migration_names_selected_directories_and_templates():
    assert migration_paths(
        ["部门/财务/", "销售/日报.v2.CPT", "部门/财务/", "总览.fvs"], "_uat_20261109"
    ) == [
        ("部门/财务/", "财务_uat_20261109/"),
        ("销售/日报.v2.CPT", "日报.v2_uat_20261109.CPT"),
        ("总览.fvs", "总览_uat_20261109.fvs"),
    ]
