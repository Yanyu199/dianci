<template>
  <el-container class="app-container">
    <el-header class="sys-header">
      <div class="logo-title">
        <span class="logo-icon">⚡</span>
        TEM瞬变电磁数据处理系统
      </div>
      <el-menu
        mode="horizontal"
        :router="true"
        default-active="/data-process/xy"
        class="sys-menu"
        :ellipsis="false"
      >
        <el-menu-item index="/data-process/xy">数据预处理 (X/Y)</el-menu-item>
        <el-menu-item index="/about" disabled>反演计算 (开发中)</el-menu-item>
        <el-menu-item index="/about" disabled>3D 成果展示 (开发中)</el-menu-item>
      </el-menu>
    </el-header>

    <el-main class="sys-main"> <router-view /> </el-main>
  </el-container>
</template>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.sys-header {
  background-color: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  padding: 0 20px;
  z-index: 10;
}

.logo-title {
  font-size: 20px;
  font-weight: bold;
  color: #2c3e50;
  margin-right: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sys-menu {
  flex-grow: 1;
  border-bottom: none !important;
}

.sys-main {
  background-color: transparent;
  padding: 20px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}
</style>
