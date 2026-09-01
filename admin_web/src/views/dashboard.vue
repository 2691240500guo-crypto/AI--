<template>
  <div class="cards">
    <el-card class="c">
      <el-statistic title="在职人数" :value="126" />
    </el-card>
    <el-card class="c">
      <el-statistic title="本月测评" :value="48" />
    </el-card>
    <el-card class="c">
      <el-statistic title="待办推送" :value="12" />
    </el-card>
    <el-card class="c">
      <el-statistic title="岗位匹配" :value="36" />
    </el-card>
    <el-card style="width:100%">
      <template #header>欢迎回来</template>
      <p>这里是 AI 人才平台管理端看板占位。数据源（F01）在二期接入。</p>
    </el-card>
  </div>
</template>

<style scoped>
.cards { display: flex; flex-wrap: wrap; gap: 16px; }
.c { width: 240px; }
</style>