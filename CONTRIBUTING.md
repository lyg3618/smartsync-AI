# 贡献指南

感谢你愿意帮助改进 SmartSync。你可以提交缺陷报告、功能建议、文档改进或代码贡献。

## 提交问题

- 提交前请先搜索现有 Issue，避免重复。
- 缺陷报告应包含复现步骤、预期行为、实际行为、运行环境和必要的日志。
- 日志、截图和配置文件中请删除密码、访问令牌、会议内容、联系人信息等敏感数据。
- 安全漏洞不要提交公开 Issue，请遵循 [安全说明](SECURITY.md)。

## 开发流程

1. Fork 仓库并从默认分支创建功能分支。
2. 按照 [README](README.md) 完成本地环境配置。
3. 保持修改范围清晰，不要在同一个 Pull Request 中混入无关重构。
4. 为行为变更补充或更新测试，并同步更新相关文档和环境变量示例。
5. 提交 Pull Request，说明修改动机、实现方式、验证结果和可能的兼容性影响。

建议使用容易理解的分支名，例如 `feature/meeting-export`、`fix/upload-limit` 或 `docs/deployment-guide`。

## 本地验证

后端测试：

```powershell
Set-Location backend
python -m pytest -q
```

前端构建：

```powershell
Set-Location frontend
npm ci
npm run build
```

涉及 Docker 部署时，请额外验证配置：

```powershell
docker compose config
docker compose up -d --build
```

## Pull Request 检查清单

- [ ] 修改目标和范围已经清楚说明。
- [ ] 没有提交 `.env`、密钥、真实会议数据、录音或个人信息。
- [ ] 相关测试和构建已经通过。
- [ ] 文档、配置示例和数据库迁移已按需更新。
- [ ] 新增依赖确有必要，并已核对其许可证和安全风险。

提交贡献即表示你同意按照项目的 [MIT License](LICENSE) 授权你的贡献。
