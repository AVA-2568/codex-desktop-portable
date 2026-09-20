# Codex / ChatGPT Desktop — Portable for Older Windows

Unofficial **portable packages** of the official OpenAI **ChatGPT (Codex) desktop app for Windows**, for machines that fail the official installer's OS check — for example **Windows 10 LTSC 2019 (build 17763 / 1809)**.

> The official MSIX declares `MinVersion 10.0.19041`, so Microsoft Store / `Add-AppxPackage` refuse to install on older builds with error `0x80073CFD` ("prerequisites not met"). In practice the app itself runs on older builds — the version gate lives in the installer metadata, not in the app. This project removes exactly that barrier by extracting the **unmodified** app from the **official** package. Tested working on Windows 10 build 17763.

## What a release contains

| Asset | Description |
|---|---|
| `ChatGPT-Codex-win-x64-portable.zip` | The extracted app folder. Unzip anywhere → run `ChatGPT-Codex\ChatGPT.exe` |
| `ChatGPT-x64.msix` | The **original, untouched** MSIX downloaded from OpenAI's CDN |

## Quick start

1. Download `ChatGPT-Codex-win-x64-portable.zip` from the [latest release](../../releases/latest)
2. Right-click → *Extract All*
3. Run `ChatGPT-Codex\ChatGPT.exe`, sign in with your ChatGPT account

Or do the same automatically on any Windows 10+ machine:

```powershell
.\build.ps1              # download latest from OpenAI CDN -> extract -> desktop shortcut
.\build.ps1 -Arch arm64  # ARM64 variant
```

## Requirements

- Windows 10/11 x64 (or arm64) — **build 17763 (1809) tested working**; ≥ 1809 expected
- No Microsoft Store, no winget, no admin rights required

## How it works

```
official MSIX (signed ZIP container) ──extract──▶ app\ ──▶ run ChatGPT.exe directly
```

An MSIX is a ZIP archive signed by OpenAI/Microsoft. Extracting it needs no admin rights, no modification, and no repacking — the app simply runs without the package-identity checks that the installer enforces.

## Weekly automation

A scheduled GitHub Actions workflow checks OpenAI's CDN **every Monday**; when the version on the CDN differs from the latest release here, it extracts, packages, and publishes a new release automatically. You can also trigger it manually: **Actions → Weekly release check → Run workflow**.

**Versioning** — release tags mirror the **official in-app version** (read from `version` in `resources/app.asar` → `package.json`, the same number the app reports at runtime). Note that the MSIX *container* version declared in `AppxManifest.xml` (e.g. `26.915.4065.0`) is a different, packaging-side number and is intentionally not used as the release tag.

**Retention** — only the **3 most recent releases** are kept. After every run, older releases (and their tags) are pruned automatically.

## Updating

- Re-run `build.ps1` — it always installs the newest version from OpenAI's CDN.
- Or download the latest portable zip from the [latest release](../../releases/latest) and replace the app folder.
- Alternatively, updates can be applied with [**CC Switch**](https://github.com/farion1231/cc-switch).

## App data

App data lives in `%LOCALAPPDATA%\Codex` — outside the app folder — so replacing or moving the folder does not affect your login state.

## Limitations

- **No auto-update**: the official updater only works inside the MSIX install. Re-run `build.ps1`, grab a newer release, or use CC Switch to update (see [Updating](#updating)).
- This is the desktop **app**. The Codex CLI (`npm i -g @openai/codex`) is a separate product with different system requirements.

## 中文说明

本项目为 **OpenAI ChatGPT（Codex）Windows 桌面应用**的非官方便携包，用于绕过官方安装包的最低系统版本检查（`MinVersion 10.0.19041`），让 **Windows 10 LTSC 2019（build 17763 / 1809）** 等旧版本系统也能使用。

- 官方 MSIX 要求 build ≥ 19041，否则安装报 `0x80073CFD`；但应用本体实际可在 1809 上正常运行（已实测）
- 原理：MSIX 本质是签名的 ZIP 容器，解包后直接运行 `app\ChatGPT.exe`，不做任何修改、不重新签名、无需管理员权限
- 用法：下载 Release 中的 `ChatGPT-Codex-win-x64-portable.zip` 解压运行；或在 Windows 上运行 `.\build.ps1` 一键完成"下载官方包 → 解包 → 创建桌面快捷方式"
- 每周一自动检查 OpenAI CDN 新版本并自动发布 Release
- **版本对齐**：Release 版本号与官方应用内版本一致（取自应用包内 `resources/app.asar` → `package.json` 的 `version`，即应用自身运行时报告的版本号）。MSIX 容器版本（`AppxManifest.xml` 中的版本，如 `26.915.4065.0`）是打包侧的另一个编号，不作为发布版本号
- **保留策略**：仅保留最近 **3** 个 Release，更早的版本（含对应 tag）在每次运行后自动清理
- **更新方式**：重新运行 `.\build.ps1`、下载最新 Release 替换应用目录，或使用 [**CC Switch**](https://github.com/farion1231/cc-switch) 更新
- 应用数据存于 `%LOCALAPPDATA%\Codex`，更新替换不影响登录状态

## Disclaimer

This repository does **not** modify, patch, or re-sign any OpenAI software. It automates downloading and unzipping the **official** package and redistributes it **unmodified**, solely so that users on system versions OpenAI no longer supports can still run it. All application binaries are © OpenAI and subject to OpenAI's terms. Use at your own risk; issues will be honored with immediate takedown upon a valid request.
