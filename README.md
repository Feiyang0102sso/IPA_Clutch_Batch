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

IPA Clutch Batch is a Windows-focused batch cracking assistant for jailbroken iOS devices. It lets you run the whole IPA cracking workflow from your computer: batch install IPA files, batch run Clutch, then pull all dumped IPA files back and rename them automatically. No more staring at a console and manually installing, reinstalling, and typing commands for every single app. Faster, cleaner, and a little less painful. **🤓👍**

### What It Does

The batch workflow is intentionally simple:

1. Install IPA files one by one.
2. Run Clutch on each installed app one by one.
3. Wait until all apps have been processed.
4. Export all dumped IPA files back to the computer.
5. Batch rename the exported IPA files using their metadata.

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

### Prerequisites

The following example uses iOS 6 as the target environment.

1. Use a jailbroken iOS device.
2. Install the following packages on the device:
   - `afc2`
   - `OpenSSH`
   - `Core Utilities`
3. Download the latest Clutch release from GitHub:
   - [KJCracks/Clutch releases](https://github.com/KJCracks/Clutch/releases)
4. Rename the Clutch binary to `Clutch`.
5. Copy `Clutch` to `/usr/bin/` on the device.
6. Give `Clutch` executable permission.

### References

- [iOS6 skill: cracking IPA files, only for iOS 6-10 jailbroken devices](https://www.bilibili.com/video/BV1FLWYeLEQj) This video will teach you step by step how to install Clutch onto your iPhone/iPad.
- If you want to recover IPA files for apps you previously downloaded or purchased, including some delisted apps, see this discussion: [52pojie thread](https://www.52pojie.cn/thread-2074404-1-1.html). The related project is [wf021325/ipatool.js](https://github.com/wf021325/ipatool.js).

I do not currently know whether there is a matching English tutorial on YouTube.

### Version History

| Version | Notes |
| --- | --- |
| 0.1.0 | Initial release. |

------

<a id="chinese-version"></a>
## 🇨🇳 中文版

> [!CAUTION]
> 本项目仅供学习、研究和个人归档使用。
> 请只处理你合法拥有且被允许检查的 IPA 文件。
> 你需要自行遵守当地法律、软件许可协议和平台规则。

IPA Clutch Batch 是一个面向 Windows 的电脑端批量砸壳助手，用于配合已越狱的 iOS 设备批量处理 IPA 文件。它可以在电脑上一口气完成批量安装、批量调用 Clutch 砸壳、统一拉回导出的 IPA 文件，并自动批量重命名。不用再像以前一样一直盯着控制台，一个个安装、重新安装、手动输入命令。更快，更省事，也更少折磨。**🤓👍**

### 项目做什么

批量流程刻意保持简单：

1. 一个个安装 IPA 文件。
2. 一个个对已安装的 App 执行 Clutch 砸壳。
3. 等待全部 App 处理完成。
4. 将所有砸壳后的 IPA 文件统一导出到电脑。
5. 根据 IPA 元数据批量重命名导出的文件。

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

### 前置条件

以下以 iOS 6 环境为例。

1. 准备一台已越狱的 iOS 设备。
2. 在设备上安装以下插件：
   - `afc2`
   - `OpenSSH`
   - `Core Utilities`
3. 从 GitHub 下载最新版 Clutch：
   - [KJCracks/Clutch releases](https://github.com/KJCracks/Clutch/releases)
4. 将 Clutch 二进制文件重命名为 `Clutch`。
5. 将 `Clutch` 放到设备的 `/usr/bin/` 目录。
6. 给 `Clutch` 赋予执行权限。

### 参考资料

- [iOS6技能之【砸壳ipa文件】，仅适用于iOS6-10已越狱设备](https://www.bilibili.com/video/BV1FLWYeLEQj) 这个视频会一步步教你如何把 Clutch 安装到 iPhone/iPad 上。
- 如果你想找回曾经下载过或购买过的 App IPA，包括部分已经下架的项目，可以参考这个帖子：[52pojie thread](https://www.52pojie.cn/thread-2074404-1-1.html)。相关项目仓库是：[wf021325/ipatool.js](https://github.com/wf021325/ipatool.js)。

我目前不确定 YouTube 上是否有对应的英文教程。

### 版本历史

| 版本 | 说明 |
| --- | --- |
| 0.1.0 | 初始版本。 |
