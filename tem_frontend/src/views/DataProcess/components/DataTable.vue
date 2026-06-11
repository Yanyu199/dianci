<template>
  <div class="table-wrapper">
    <div class="table-header">
      <h3>📋 归一化二次场感应电动势明细数据</h3>
    </div>
    <el-table :data="tableData" border height="100%" stripe style="width: 100%">
      <el-table-column prop="time" label="采样时间 t (ms)" width="130" fixed />
      <el-table-column v-for="p in 9" :key="p" :label="`测点 ${p}`" align="center">
        <el-table-column
          :prop="`x_p${p}`"
          label="X分量(μV)"
          width="110"
          :formatter="formatScientific"
        />
        <el-table-column
          :prop="`y_p${p}`"
          label="Y分量(μV)"
          width="110"
          :formatter="formatScientific"
        />
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  tableData: any[]
}>()

const formatScientific = (row: any, column: any, cellValue: number) => {
  if (cellValue === 0 || !cellValue) return '0.0000e+0'
  return cellValue.toExponential(4)
}
</script>

<style scoped>
.table-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 10px;
}
.table-header {
  margin-bottom: 10px;
  color: #303133;
}
.table-header h3 {
  margin: 0;
  font-size: 16px;
  border-left: 4px solid #67c23a;
  padding-left: 8px;
}
</style>
