# IPA Clutch Batch

🌍 **Language / 语言**

- [🇺🇸 English Version](#english-version)
- [🇨🇳 中文版](#chinese-version)

------

<a id="english-version"></a>
## 🇺🇸 English Version

> [!CAUTION]
> This project is provided for learning, research, and personal archival purposes only.
> Only process IPA files that you legally own and are allowed to inspect.
> You are responsible for complying with local laws, software licenses, and platform rules.

IPA Clutch Batch is a Windows-focused batch cracking assistant for jailbroken iOS devices. It lets you run the whole IPA cracking workflow from your computer: install one IPA, run Clutch, pull the dumped IPA back, rename it, clean up the remote dump, then continue with the next file. No more staring at a console and manually installing, reinstalling, and typing commands for every single app. Faster, cleaner, and a little less painful. **🤓👍**

### What It Does

The tool first establishes SSH communication with the device, then checks and repairs the Clutch status.

The batch workflow then remains intentionally simple:

1. Install one IPA file.
2. Run Clutch on the installed app.
3. Download and rename the dumped IPA on the computer.
4. Verify the local file and remove its remote dump.
5. Continue with the next IPA file.

### Environment

- Python 3.10
- Runtime dependency:
  - `paramiko`
- Build dependencies:
  - `Nuitka`
  - `ordered-set`
- Packaging:
  - Built with Nuitka one-file mode.

This project also uses the Windows build of `libimobiledevice` from:

- [L1ghtmann/libimobiledevice releases](https://github.com/L1ghtmann/libimobiledevice/releases)

### How To Use

Drag the folder that contains your IPA files onto the BAT file.

The tool will scan the folder, process the IPA files, and place the renamed dumped files into the output folder created by the program.

Normal batch processing hides complete logs by default. Standalone modes show regular logs. See the table below for available arguments.

| Argument | Description |
| --- | --- |
| `input_path` | IPA directory; required for normal batch processing. |
| `--verbose` | Show complete console logs instead of progress bars during normal batch processing. |
| `--clutch` | Only check the Clutch environment; do nothing else. |
| `--ssh22` | Open local port 22 for testing. It cannot be combined with any other argument; press `Ctrl+C` to close the connection. |
| `-h`, `--help` | Show command help. |

### Prerequisites

The following example uses iOS 6 as the target environment.

1. Use a jailbroken iOS device.
2. Install the following packages on the device:
   - `afc2`
   - `OpenSSH`
   - `Core Utilities`
3. Optional: install Clutch manually if you want to prepare it yourself:
   - [KJCracks/Clutch releases](https://github.com/KJCracks/Clutch/releases)
4. For manual installation, rename the Clutch binary to `Clutch`.
5. Copy `Clutch` to `/usr/bin/` on the device and grant it executable permission.
6. The tool will check the Clutch status and repair it when the required conditions are not met.

### References

- [iOS6 skill: cracking IPA files, only for iOS 6-10 jailbroken devices](https://www.bilibili.com/video/BV1FLWYeLEQj) This video will teach you step by step how to install Clutch onto your iPhone/iPad.
- If you want to recover IPA files for apps you previously downloaded or purchased, including some delisted apps, see this discussion: [52pojie thread](https://www.52pojie.cn/thread-2074404-1-1.html). The related project is [wf021325/ipatool.js](https://github.com/wf021325/ipatool.js).

I do not currently know whether there is a matching English tutorial on YouTube.

### Version History

| Version | Date | Notes |
| --- | --- | --- |
| 1.0.0 | 2026-07-18 | - Added console progress bars.<br>- Added Clutch checks and repair.<br>- Changed batch processing to install one IPA, crack one app, transfer and rename the dump, then remove the dump to save device storage. |
| 0.1.0 | 2026-07-17 | init release |

------

<a id="chinese-version"></a>
## 🇨🇳 中文版

> [!CAUTION]
> 本项目仅供学习、研究和个人归档使用。
> 请只处理你合法拥有且被允许检查的 IPA 文件。
> 你需要自行遵守当地法律、软件许可协议和平台规则。

IPA Clutch Batch 是一个面向 Windows 的电脑端批量砸壳助手，用于配合已越狱的 iOS 设备批量处理 IPA 文件。它会依次完成安装一个 IPA、调用 Clutch 砸壳、拉回并重命名导出的 IPA、清理设备端 dump，然后再处理下一个文件。不用再像以前一样一直盯着控制台，一个个安装、重新安装、手动输入命令。更快，更省事，也更少折磨。**🤓👍**

### 项目做什么

程序会先与手机建立 SSH 通信，并检查与修补 Clutch 状态。

之后的批量流程刻意保持简单：

1. 安装一个 IPA 文件。
2. 对已安装的 App 执行 Clutch 砸壳。
3. 将 dump 下载到电脑并根据元数据重命名。
4. 验证本地文件并删除对应的设备端 dump。
5. 继续处理下一个 IPA 文件。

### 运行环境

- Python 3.10
- 运行依赖：
  - `paramiko`
- 打包依赖：
  - `Nuitka`
  - `ordered-set`
- 打包方式：
  - 使用 Nuitka one-file 模式打包。

本项目还使用了 Windows 版本的 `libimobiledevice`：

- [L1ghtmann/libimobiledevice releases](https://github.com/L1ghtmann/libimobiledevice/releases)

### 使用方式

直接把包含 IPA 文件的文件夹拖到 BAT 文件上。

程序会扫描该文件夹，依次处理 IPA 文件，并将重命名后的砸壳文件放到程序创建的输出文件夹中。

正常批处理默认不会完整打印所有日志；独立模式会正常输出日志。具体参数详见下表。

| 参数 | 说明 |
| --- | --- |
| `input_path` | IPA 文件夹路径；正常批处理时必填。 |
| `--verbose` | 正常批处理时显示完整控制台日志，不显示进度条。 |
| `--clutch` | 仅对 Clutch 环境进行检查，不执行其他操作。 |
| `--ssh22` | 打开本地 22 端口用于测试；不可与任何其他参数同时使用，按 `Ctrl+C` 关闭连接。 |
| `-h`, `--help` | 显示命令帮助。 |

### 前置条件

以下以 iOS 6 环境为例。

1. 准备一台已越狱的 iOS 设备。
2. 在设备上安装以下插件：
   - `afc2`
   - `OpenSSH`
   - `Core Utilities`
3. 可选：如果你希望自行准备 Clutch，依然可以手动安装：
   - [KJCracks/Clutch releases](https://github.com/KJCracks/Clutch/releases)
4. 手动安装时，将 Clutch 二进制文件重命名为 `Clutch`。
5. 将 `Clutch` 放到设备的 `/usr/bin/` 目录并赋予其执行权限。
6. 程序会检测 Clutch 状态，并在条件未达标时进行修补。

### 参考资料

- [iOS6技能之【砸壳ipa文件】，仅适用于iOS6-10已越狱设备](https://www.bilibili.com/video/BV1FLWYeLEQj) 这个视频会一步步教你如何把 Clutch 安装到 iPhone/iPad 上。
- 如果你想找回曾经下载过或购买过的 App IPA，包括部分已经下架的项目，可以参考这个帖子：[52pojie thread](https://www.52pojie.cn/thread-2074404-1-1.html)。相关项目仓库是：[wf021325/ipatool.js](https://github.com/wf021325/ipatool.js)。

我目前不确定 YouTube 上是否有对应的英文教程。

### 版本历史

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 1.0.0 | 2026-07-18 | - 增加 console 进度条。<br>- 增加 Clutch 检测与修补。<br>- 批处理改为安装一个、砸壳一个、转移并重命名到电脑后删除 dump，减少手机存储占用。 |
| 0.1.0 | 2026-07-17 | init release |
