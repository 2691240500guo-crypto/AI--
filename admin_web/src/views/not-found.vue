<template>
  <div class="nf">
    <h2>404</h2>
    <p>页面不存在或没有访问权限</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </div>
</template>

<style scoped>
.nf { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; background: #f5f7fa; }
.nf h2 { font-size: 48px; margin: 0; color: #d0d7e2; }
.nf p { color: #6b7280; margin: 0 0 12px; }
</style>
