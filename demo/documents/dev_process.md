---
title: 研发流程规范
doc_type: SOP
tags: [development, process, git, review, ci-cd]
version: 2.1
author: Engineering Team
---

# 研发流程规范

## 1. 分支管理

### 1.1 分支策略 (GitFlow)
- `main`: 生产就绪代码
- `develop`: 开发集成分支
- `feature/*`: 功能开发
- `release/*`: 发布准备
- `hotfix/*`: 紧急修复

### 1.2 命名规范
- Feature: `feature/TICKET-123_short-description`
- Bugfix: `fix/TICKET-456_bug-description`
- Hotfix: `hotfix/PROD-789_critical-issue`

## 2. 代码审查

### 2.1 PR 要求
- 至少 1 名 reviewer 批准
- 所有 CI 检查通过
- 无未解决的评论
- 变更不超过 400 行（建议）

### 2.2 审查清单
- [ ] 代码风格符合规范
- [ ] 单元测试已添加
- [ ] 文档已更新
- [ ] 无安全漏洞
- [ ] 无敏感信息硬编码

## 3. CI/CD 流程

### 3.1 CI 阶段
```
代码推送 → Lint → 单元测试 → 集成测试 → 构建 → 镜像推送
```

### 3.2 CD 阶段
```
开发环境 → 测试环境 → 预发布环境 → 生产环境
```

### 3.3 部署策略
- 开发环境: 自动部署
- 测试环境: 自动部署
- 预发布环境: 手动触发
- 生产环境: 审批 + 手动触发

## 4. 质量标准

### 4.1 代码质量
- ESLint/Prettier 通过
- 测试覆盖率 > 80%
- 无已知安全漏洞

### 4.2 性能标准
- API P99 延迟 < 200ms
- 页面加载 < 3s
- 数据库查询 < 100ms
- 内存泄漏检测通过

## 5. 发布流程

### 5.1 发布检查清单
- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 性能测试通过
- [ ] 安全扫描通过
- [ ] 变更日志已更新
- [ ] 回滚方案已准备

### 5.2 回滚流程
1. 识别问题版本
2. 执行 `git revert` 或回退镜像
3. 触发紧急部署
4. 验证恢复状态