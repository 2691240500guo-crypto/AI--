# asm_result 身份字段迁移说明

## 目标

Alembic revision `c9d4e7f1a203` 将测评记录中的两种身份明确分开：

- `asm_result.talent_id` 外键指向 `tal_talent.id`，用于人才档案、统计、报告和培训联动。
- `asm_result.user_id` 外键指向 `sys_user.id`，用于登录鉴权和消息投递。

迁移通过 `sys_user.talent_id` 建立 `user_id -> talent_id` 映射。迁移兼容两类存量库：

1. 旧 `talent_id` 外键仍指向 `sys_user.id`；
2. `talent_id` 已提前改为指向 `tal_talent.id`，但还没有 `user_id`。

没有外键的手工库只有在每条记录都能唯一映射时才会继续。缺失映射或一份人才档案关联多个账号时，迁移会在改写业务数据前中止并报告对应 `result_id`。

## 上线步骤

1. 停止会写入 `asm_result` 的后端实例和定时任务。
2. 先检查账号与人才档案映射是否缺失或重复：

   ```sql
   SELECT id, username
   FROM sys_user
   WHERE talent_id IS NULL;

   SELECT talent_id, COUNT(*) AS account_count
   FROM sys_user
   WHERE talent_id IS NOT NULL
   GROUP BY talent_id
   HAVING COUNT(*) > 1;
   ```

3. 确认 `.env` 中 `DATABASE_URL` 指向目标数据库，然后执行：

   ```powershell
   $env:PYTHONUTF8 = "1"
   alembic upgrade c9d4e7f1a203
   ```

4. 验证迁移结果：

   ```sql
   SELECT COUNT(*) FROM asm_result;
   SELECT COUNT(*) FROM asm_result_identity_backup;

   SELECT r.id, r.user_id, r.talent_id
   FROM asm_result r
   LEFT JOIN sys_user u ON u.id = r.user_id
   LEFT JOIN tal_talent t ON t.id = r.talent_id
   WHERE u.id IS NULL
      OR t.id IS NULL
      OR u.talent_id IS NULL
      OR u.talent_id <> r.talent_id;
   ```

   前两个数量应相同，最后一条查询应返回 0 行。

## 备份与回滚

升级会创建并保留以下迁移专用表：

- `asm_result_identity_backup`：保存迁移前每条结果的 `talent_id` 和已有的 `user_id`。
- `asm_result_identity_backup_meta`：保存迁移前字段、索引和外键状态。

不要在升级后手工删除或修改这两张表。需要回滚时，从 revision `c9d4e7f1a203` 执行：

```powershell
$env:PYTHONUTF8 = "1"
alembic downgrade -1
```

`downgrade()` 会先用备份恢复原值和原外键语义，成功后才删除迁移备份表。若备份缺失，迁移会拒绝执行不可恢复的回滚。
