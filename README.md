# lazy-commit

让 AI 帮你写 Git 提交信息。支持 macOS、Windows、Linux 和 WSL。

## 1. 安装并配置

准备好 **Git** 和你的模型服务 **API Key**，打开终端，复制对应命令：

**macOS / Linux / WSL**

```sh
curl -fsSL https://raw.githubusercontent.com/Kingsmai/lazy-commit/main/scripts/install.sh | sh
```

**Windows PowerShell**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Kingsmai/lazy-commit/main/scripts/install.ps1 | iex"
```

安装完成会自动打开配置向导：选择语言 → 选择模型服务 → 填写模型和 API Key → 确认保存。
按回车使用默认值，按 `Ctrl+C` 可取消。完成后重新打开终端。
无需安装 Python，无需手动设置环境变量。

> API Key 从你使用的模型服务控制台获取。输入时不会显示字符，保存于用户目录的配置文件中（明文），不会写入项目。向导保存配置，不会调用模型。

如果向导没有自动打开，重开终端运行：

```sh
lazy-commit --setup
```

## 2. 开始使用

在你的 **Git 项目目录** 打开终端，预览 AI 生成的提交信息：

```sh
lazy-commit
```

想把所有改动暂存并提交？运行下面的命令，检查生成的信息，再确认：

```sh
lazy-commit --apply --stage-all
```

## 以后怎么用？

| 我想…… | 怎么做 |
| --- | --- |
| 修改 API Key、模型或语言 | `lazy-commit --setup` |
| 使用可操作的全屏界面 | `lazy-commit --tui` |
| 更新版本 | 重新运行上面的安装命令 |
| 卸载 | `uv tool uninstall lazy-commit` |

**遇到问题？** 提示找不到 Git 时先安装 Git；提示找不到 `lazy-commit` 时重开终端。
API 报错时运行 `lazy-commit --setup` 核对服务地址、模型名称和密钥。
已有环境变量会优先于向导保存的配置。

更多内容：[完整参数与配置](docs/REFERENCE.md) · [参与开发](CONTRIBUTING.md)

MIT License · 当前版本 `0.13.0`
