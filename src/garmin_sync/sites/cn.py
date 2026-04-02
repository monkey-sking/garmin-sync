from garmin_sync.sites.base import GarminSiteAdapter


class GarminChinaAdapter(GarminSiteAdapter):
    def __init__(self) -> None:
        super().__init__(
            key="cn",
            label="Garmin China",
            import_url="https://connect.garmin.cn/modern/import-data",
            file_input_selectors=(
                "input[type='file']",
            ),
            submit_button_selectors=(
                "button:has-text('导入数据')",
                "[role='button']:has-text('导入数据')",
            ),
            success_markers=("success", "completed", "imported", "成功", "完成"),
            duplicate_markers=("duplicate", "already exists", "已存在", "重复", "此文件已上传"),
            failure_markers=("failed", "error", "失败", "错误"),
        )
