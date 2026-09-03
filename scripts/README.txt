AI Talent 启动/关闭脚本说明
==========================

文件位置: scripts\

一、脚本清单
------------
  start-backend.bat       启动后端 (FastAPI, 端口 8000, 热重载)
  stop-backend.bat        关闭后端 (结束占用 8000 的进程)
  start-admin-web.bat     启动管理端 (Vue3 + Element Plus, 端口 5173)
  stop-admin-web.bat      关闭管理端 (结束占用 5173 的进程)
  start-miniapp.bat       启动小程序 H5 (uni-app, 端口 5174)
  stop-miniapp.bat        关闭小程序 H5 (结束占用 5174 的进程)
  stop-all-frontend.bat   一键关闭两个前端 (5173 + 5174)
  seed_assessment_data.py 幂等补齐 C 测评演示数据，不删除已有结果
  reset_assessment_data.py 删除并重新生成 C 测评演示业务数据
  audit_database_schema.py 只读生成完整数据库表/字段审计清单

二、使用方式
------------
  全部双击即可,无需手动敲命令。建议按顺序: 后端 → 管理端 → 小程序。

  1. 启动后端:    双击 start-backend.bat
     自动使用 C:\miniconda3 的 Python, 连接云端 MySQL
     API 文档: http://127.0.0.1:8000/docs
     首次运行会自动 pip install 后端依赖 (清华镜像)

  2. 启动管理端:  双击 start-admin-web.bat
     浏览器自动打开 http://127.0.0.1:5173
     默认账号: admin / admin123
     首次运行会自动 npm install (国内镜像源)

  3. 启动小程序:  双击 start-miniapp.bat
     浏览器自动打开 http://127.0.0.1:5174/#/pages/index/index

  4. 关闭: 双击对应的 stop-*.bat,或直接关掉启动时弹出的黑窗口
     (dev server / uvicorn 窗口用 Ctrl+C 关闭更干净)

  5. 幂等补齐测评演示数据:
     python scripts\seed_assessment_data.py

  6. 删除旧测评演示业务数据并按当前模型重新生成:
     先确认 .env 的 DATABASE_URL 指向目标数据库,再执行
     python scripts\reset_assessment_data.py --yes
     重建只删除固定种子名称对应的 C 测评题库、试卷、批次、结果、报告和联动记录。
     演示登录账号与人才档案会保留,避免影响消息、培训等其他模块。

  7. 生成数据库表/字段审计清单:
     python scripts\audit_database_schema.py
     默认输出 docs\数据库表字段审计清单.md,不会输出数据库地址、密码或业务行内容。

三、端口对照
------------
  5173  管理端 (Vite)
  5174  小程序 H5 (Vite)
  8000  后端 API (FastAPI)

四、常见问题
------------
  Q: 提示"端口已被占用,可能已在运行"?
  A: 先双击对应的 stop-*.bat 关掉旧进程,再启动。

  Q: 启动后页面打不开或 502?
  A: 管理端 /api 代理到 127.0.0.1:8000,请确认先启动了后端。

  Q: 首次 npm install / pip install 很慢?
  A: 脚本已自动使用国内镜像源 (npmmirror / 清华 PyPI)。
     如仍中断,删除对应目录的 node_modules 后重试。

  Q: 后端启动报数据库连接错误?
  A: 后端连的是共享云端 MySQL (120.77.177.232), 配置在项目根 .env。
     如更换数据库, 修改 .env 的 DATABASE_URL 即可。

  Q: 双击后出现一堆乱码报错(如 "'€?'/'cho.' 不是内部或外部命令")?
  A: 脚本编码被改坏了。所有 *.bat 必须保存为 ANSI/GBK 编码 +
     Windows 换行(CRLF), 且保留第一行 @echo off 与第二行 chcp 936 >nul。
     不要用 UTF-8 / 带 BOM / Linux 换行(LF) 保存:
     - UTF-8 会被 cmd 按 GBK 解析导致乱码;
     - 纯 LF 换行会导致命令被"吃掉"、rem 行被当命令执行;
     - 括号块(if/for 的圆括号内)里的 echo 文本也不能含圆括号 ( )
       (如 "端口 (8000)" 需写成 "端口 [8000]")。
     用记事本编辑后: 另存为 -> 编码选 "ANSI"(自动带 CRLF) 即可。
