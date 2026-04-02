from garmin_sync.sites.cn import GarminChinaAdapter
from garmin_sync.sites.global_site import GarminGlobalAdapter


def get_site_adapter(site: str):
    if site == "cn":
        return GarminChinaAdapter()
    if site == "global":
        return GarminGlobalAdapter()
    raise ValueError(f"Unsupported site: {site}")
