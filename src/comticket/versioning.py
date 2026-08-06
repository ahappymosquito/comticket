"""职责：提供不依赖外部服务的组件版本号处理工具。"""


def bump_version(version_num: str) -> str:
    """将版本号的 patch 段加一，并处理进位。"""
    version_parts = version_num.split(".")
    if len(version_parts) == 2:
        version_parts.append("0")

    version_parts[-1] = str(int(version_parts[-1]) + 1)
    for index in range(len(version_parts) - 1, -1, -1):
        if int(version_parts[index]) < 10:
            continue
        version_parts[index] = "0"
        if index > 0:
            version_parts[index - 1] = str(int(version_parts[index - 1]) + 1)
        else:
            version_parts.insert(0, "1")

    return ".".join(version_parts)
