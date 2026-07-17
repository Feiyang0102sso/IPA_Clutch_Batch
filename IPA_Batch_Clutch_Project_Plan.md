# iOS IPA 批量安装与 Clutch 砸壳工具项目计划

## 1. 项目目标

本项目用于在 Windows 上批量处理一个指定输入目录中的 IPA 文件：

1. 从 `INPUT_DIR` 读取所有待安装 IPA。
2. 按文件名字母表顺序逐个安装到已越狱 iPhone。
3. 每次安装后，通过 SSH 调用手机上的 Clutch 进行砸壳。
4. 安装覆盖不区分新旧版本：同 Bundle ID 的应用直接覆盖安装。
5. 整个输入目录全部处理完成后，再统一从 Clutch dump 目录导出砸壳结果。
6. 读取导出的 IPA 内部 `Info.plist`。
7. 根据 `Info.plist` 批量重命名，并统一添加 `_cracked` 后缀。
8. 所有最终产物放到 `INPUT_DIR/Cracked/`。

当前阶段优先保证流程稳定，不追求完全摆脱第三方工具。

---

## 2. 目录模型

目录只围绕输入目录展开。

```text
INPUT_DIR/
├── Contract Kill2_0.1.0.ipa
├── Contract Kill2_0.2.0.ipa
├── Contract Kill2_1.0.0.ipa
└── Cracked/
    ├── Contract_Killer_2_0.1.0_cracked.ipa
    ├── Contract_Killer_2_0.2.0_cracked.ipa
    └── Contract_Killer_2_1.0.0_cracked.ipa
```

规则：

- `INPUT_DIR` 是唯一需要指定的业务目录。
- 程序只扫描 `INPUT_DIR` 第一层的 `*.ipa` 文件。
- 程序不递归扫描子目录。
- `Cracked/` 固定由 `INPUT_DIR / "Cracked"` 得出。
- 如果以后允许用户传入其他输入目录，`Cracked/` 也会自动跟着变成该目录下的 `Cracked/`。
- 不再单独维护 `output/`、`reports/`、根目录 `Cracked/` 等目录。

---

## 3. 核心流程

```text
启动程序
    -> 检查工具和目录
    -> 检查 SSH 通道
    -> 扫描 INPUT_DIR 第一层的 IPA
    -> 按文件名字母表顺序排序
    -> 安装第一个 IPA
    -> 等待安装命令结束
    -> 通过 SSH 调用 Clutch
    -> 等待 Clutch 命令结束
    -> 记录当前 IPA 的处理结果
    -> 安装下一个 IPA，并覆盖当前同 Bundle ID 应用
    -> 重复直到 INPUT_DIR 中所有 IPA 都处理完成
    -> 从 Clutch dump 目录统一导出所有砸壳 IPA
    -> 读取每个导出 IPA 的 Info.plist
    -> 批量重命名为 *_cracked.ipa
    -> 输出到 INPUT_DIR/Cracked/
```

---

## 4. IPA 排序规则

程序按文件名字母表顺序读取和安装 IPA。

排序规则：

- 不解析版本号。
- 不比较语义化版本。
- 不判断新版本或旧版本。
- 只按文件名进行稳定排序。

这样做的原因是安装阶段不关心版本新旧。只要 IPA 使用同一个 Bundle ID，`ideviceinstaller` 覆盖安装即可，不管是旧换新还是新换旧。

---

## 5. 覆盖安装策略

同 Bundle ID 的 IPA 直接覆盖安装。

流程中不执行卸载命令，原因是：

- 覆盖安装足以切换当前设备上的目标应用版本。
- 不需要额外等待卸载完成。
- 减少手机端状态变化。
- 降低批处理流程中断概率。

安装顺序完全由 `INPUT_DIR` 中的文件名排序决定。

---

## 6. Clutch 调用策略

每个 IPA 安装完成后调用一次手机端已验证可用的 Clutch。当前 IPA 的 Clutch 执行结束后，才继续安装下一个 IPA。

Clutch 的具体命令不写死在当前配置中。第一版可以先在实现阶段按实机验证结果决定调用方式。

需要确认的风险：

1. 覆盖安装后 Clutch 是否能识别当前已安装版本。
2. Clutch 命令成功时是否正常返回退出码。
3. Clutch 失败时是否返回非零退出码。
4. Clutch dump 目录是否固定。

---

## 7. 统一导出与重命名

统一导出发生在：

```text
INPUT_DIR 中所有 IPA 都安装并调用 Clutch 完成之后
```

导出来源是 iPhone 上 Clutch 的 dump 目录。该路径需要在实际设备上确认后写入配置。

程序读取每个导出 IPA 的：

```text
Payload/*.app/Info.plist
```

优先使用以下字段生成文件名：

```text
CFBundleDisplayName
CFBundleShortVersionString
```

如果字段缺失，则按以下顺序兜底：

应用名：

```text
CFBundleDisplayName
-> CFBundleName
-> CFBundleExecutable
-> CFBundleIdentifier 最后一段
```

版本号：

```text
CFBundleShortVersionString
-> CFBundleVersion
-> UnknownVersion
```

最终文件名统一添加 `_cracked` 后缀：

```text
{AppName}_{Version}_cracked.ipa
```

如果生成重名文件，则追加序号：

```text
Contract_Killer_2_1.1.2_cracked.ipa
Contract_Killer_2_1.1.2_cracked_2.ipa
Contract_Killer_2_1.1.2_cracked_3.ipa
```

---

## 8. 当前配置项

当前配置只保留必要路径：

```text
INPUT_DIR = ROOT_DIR / "input"
CRACKED_DIR = INPUT_DIR / "Cracked"
TOOLS_DIR = ROOT_DIR / "tools"
IDEVICEINSTALLER_PATH = TOOLS_DIR / "libimobiledevice" / "ideviceinstaller.exe"
```

其他必要配置：

```text
SSH_HOST = 127.0.0.1
SSH_PORT = 22
SSH_USERNAME = root
SSH_PASSWORD = alpine

CLUTCH_DUMP_DIR = 待实机确认
CRACKED_FILENAME_SUFFIX = _cracked
```

不要把可变路径散落在业务代码中。业务代码只读取 `INPUT_DIR` 和由它派生出的 `CRACKED_DIR`。

---

## 9. 日志

每个 IPA 都应记录：

```text
原始文件名
安装顺序
安装开始时间
安装结果
安装耗时
Clutch 开始时间
Clutch 输出
Clutch 错误输出
Clutch 退出码
Clutch 耗时
最终状态
```

建议状态：

```text
PENDING
INSTALLING
INSTALL_FAILED
CRACKING
CRACK_FAILED
CRACKED
EXPORT_PENDING
EXPORT_FAILED
RENAMED
SKIPPED
```

---

## 10. 第一版最小可用功能

第一版实现：

1. 用户手动打开爱思助手 SSH 通道。
2. 程序检查 `127.0.0.1:22` 是否可连接。
3. 扫描 `INPUT_DIR` 中的 IPA。
4. 按文件名字母表顺序安装。
5. 每次安装后调用 Clutch。
6. 等待 Clutch 完成后继续下一个 IPA。
7. 记录成功、失败和日志。
8. 全部完成后统一处理 Clutch dump 导出文件。
9. 读取 `Info.plist` 并输出到 `INPUT_DIR/Cracked/`。
10. 文件名统一添加 `_cracked` 后缀。

第一版暂不实现：

- 图形界面。
- 多设备支持。
- 自动打开爱思助手。
- 自动建立 USB SSH 通道。
- 复杂版本号排序。
- 手机端实时重命名。

---

## 11. 后续增强

后续可以加入：

- 使用 `iproxy` 自动建立 SSH 转发。
- SFTP 自动下载 Clutch dump 目录。
- 断点续作。
- 失败重试策略。

---

## 12. 主要风险

### SSH 通道中断

爱思助手关闭、设备断开或 USB 不稳定都会导致连接失败。程序应在每次调用 Clutch 前确认 SSH 可用。

### Clutch 调用方式不稳定

不同设备或 Clutch 版本的调用方式可能不同。第一版应先以实机验证结果为准。

### Clutch dump 目录不固定

不同 Clutch 版本的输出目录可能不同。需要先在目标设备上确认真实 dump 目录。

### 手机存储不足

多个 cracked IPA 可能占用数 GB 空间。批量开始前应确认手机剩余空间足够。

### 输出文件重名

多个 IPA 的 `Info.plist` 可能解析出相同名称和版本号。程序必须追加序号，避免覆盖已有结果。

---

## 13. 当前结论

当前方案固定为：

```text
INPUT_DIR 按文件名字母表读取
+
ideviceinstaller 覆盖安装
+
每个 IPA 安装后调用一次 Clutch
+
所有 IPA 处理完成后统一导出 dump 结果
+
读取 Info.plist 批量重命名
+
输出到 INPUT_DIR/Cracked/ 并添加 _cracked 后缀
```

这个流程避免在安装循环中处理复杂文件导出和重命名，让第一版先把批量覆盖安装与 Clutch 调用跑稳定。
