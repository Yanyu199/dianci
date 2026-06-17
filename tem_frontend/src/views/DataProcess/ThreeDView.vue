<template>
  <div class="threed-container">
    <div class="header-box">
      <h2>全空间三分量智能立体成像</h2>
      <el-button
        v-if="!isProcessing && !hasData"
        type="primary"
        @click="$router.push('/data-process/xy')"
      >
        ⬅️ 返回第一步处理数据
      </el-button>
    </div>

    <div v-if="hasData || isProcessing" class="control-panel">
      <el-alert
        v-if="isProcessing"
        title="🚀 正在接收第一步的数据，自动进行多维空间插值与融合，请稍候..."
        type="success"
        :closable="false"
      />
      <div v-else class="render-controls">
        <div class="control-item">
          <span class="slider-label">🧊 实体拼接大小 (消除空隙): {{ cubeSize }}</span>
          <el-slider v-model="cubeSize" :min="3" :max="30" @change="rebuildMesh"></el-slider>
        </div>
        <div class="control-item">
          <span class="slider-label">👁️ 地层透明度 (看透异常体): {{ opacity }}</span>
          <el-slider
            v-model="opacity"
            :min="0.1"
            :max="1.0"
            :step="0.05"
            @change="rebuildMesh"
          ></el-slider>
        </div>
      </div>
    </div>

    <div v-if="!hasData && !isProcessing" class="empty-state">
      <el-empty description="暂无 3D 数据。请先在第一步上传 X/Y/Z 数据并完成反演处理。" />
    </div>

    <div v-show="hasData" class="render-panel">
      <div class="toolbar">
        <span>💡 提示：左键任意翻滚，右键平移，滚轮缩放。鼠标悬浮可查看坐标与电阻率。</span>
      </div>
      <div class="canvas-wrapper" @mousemove="onMouseMove" @mouseleave="tooltipVisible = false">
        <canvas ref="canvasRef" class="three-canvas"></canvas>

        <div class="colorbar-hud">
          <div class="cb-title">电阻率 (Ω·m)</div>
          <div class="cb-scale">
            <span class="cb-val">{{ globalMaxRes.toFixed(0) }}</span>
            <div class="cb-gradient"></div>
            <span class="cb-val">{{ globalMinRes.toFixed(0) }}</span>
          </div>
        </div>

        <div
          v-if="tooltipVisible"
          class="hover-tooltip"
          :style="{ left: tooltipX + 'px', top: tooltipY + 'px' }"
        >
          <div class="tt-title">📍 空间拾取点</div>
          <div>
            <b>钻进深度 (Z):</b> <span class="tt-val">{{ hoverData.z }} m</span>
          </div>
          <div>
            <b>横向延伸 (X):</b> <span class="tt-val">{{ hoverData.x }} m</span>
          </div>
          <div>
            <b>纵向延伸 (Y):</b> <span class="tt-val">{{ hoverData.y }} m</span>
          </div>
          <hr class="tt-divider" />
          <div>
            <b>地层电阻率:</b> <span class="tt-val res">{{ hoverData.res }} Ω·m</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount, toRaw } from 'vue'
import { generate3DModel } from '@/api/dataProcess'
import { globalData } from '@/store'
import * as THREE from 'three'
import { TrackballControls } from 'three/examples/jsm/controls/TrackballControls.js'

const fileX = ref<File | null>(null)
const fileY = ref<File | null>(null)
const fileZ = ref<File | null>(null)
const allFilesSelected = computed(() => fileX.value && fileY.value && fileZ.value)

const isProcessing = ref(false)
const hasData = ref(false)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const cubeSize = ref(10)
const opacity = ref(0.85)
let rawVoxelData: any[] = []

// 全局极值，用于色带显示
const globalMinRes = ref(0)
const globalMaxRes = ref(100)

// Three.js 核心
let renderer: THREE.WebGLRenderer
let mainScene: THREE.Scene
let mainCamera: THREE.PerspectiveCamera
let controls: TrackballControls
let instancedMesh: THREE.InstancedMesh | null = null
let boundsGroup: THREE.Group | null = null
let hudScene: THREE.Scene
let hudCamera: THREE.PerspectiveCamera

// 射线拾取 (Hover)
const raycaster = new THREE.Raycaster()
const mouse = new THREE.Vector2()
const tooltipVisible = ref(false)
const tooltipX = ref(0)
const tooltipY = ref(0)
const hoverData = ref({ x: 0, y: 0, z: 0, res: 0 })

onMounted(() => {
  // 检查全局仓库中是否已经有第一步传过来的 xyz 文件
  if (globalData.fileX && globalData.fileY && globalData.fileZ) {
    // 将全局文件赋值给当前页面的响应式变量
    fileX.value = globalData.fileX
    fileY.value = globalData.fileY
    fileZ.value = globalData.fileZ

    // 自动触发底层的 3D 融合生成引擎，免去用户手动点击！
    start3DImaging()
  } else {
    // 如果没有数据（比如用户直接刷新了 3D 页面），则只初始化空的三维场景
    initThreeJS()
  }
})

const start3DImaging = async () => {
  if (!allFilesSelected.value) return
  isProcessing.value = true
  try {
    // 🌟 核心修复：使用 toRaw 剥离 Vue 3 的 Proxy 响应式代理
    // 将原生的二进制 File 对象真实地传递给后端，完美解决 422 报错
    const res = await generate3DModel(toRaw(fileX.value!), toRaw(fileY.value!), toRaw(fileZ.value!))

    if (res.status === 'success') {
      rawVoxelData = res.data
      hasData.value = true
      await nextTick()
      initThreeJS()
      rebuildMesh()
    } else {
      alert('3D 构建失败: ' + res.message)
    }
  } catch (error) {
    console.error(error)
    alert('请求后端失败，请检查网络')
  } finally {
    isProcessing.value = false
  }
}
// --- 🌟 关键视觉优化：创建带白色描边的悬浮文字，防止被背景或模型遮挡 ---
const makeTextSprite = (text: string, color: string, fontSize = 40) => {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 128
  const context = canvas.getContext('2d')!

  context.font = `Bold ${fontSize}px Arial`
  context.textAlign = 'center'
  context.textBaseline = 'middle'

  // 增加白色粗描边，保证在任何背景下都极度清晰
  context.lineWidth = 5
  context.strokeStyle = 'rgba(255, 255, 255, 0.9)'
  context.strokeText(text, 128, 64)

  // 填充核心颜色
  context.fillStyle = color
  context.fillText(text, 128, 64)

  const texture = new THREE.CanvasTexture(canvas)
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false }))
  return sprite
}

// --- 生成带有刻度的空间包围盒 ---
const buildBoundingBoxAndScales = (
  minX: number,
  maxX: number,
  minY: number,
  maxY: number,
  minZ: number,
  maxZ: number
) => {
  if (boundsGroup) mainScene.remove(boundsGroup)
  boundsGroup = new THREE.Group()

  const w = maxX - minX
  const h = maxY - minY
  const d = maxZ - minZ
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const cz = (minZ + maxZ) / 2

  // 1. 绘制包围盒线框 (加深颜色以适应白底)
  const boxGeo = new THREE.BoxGeometry(w, h, d)
  const edges = new THREE.EdgesGeometry(boxGeo)
  const boxFrame = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: 0x333333, opacity: 0.35, transparent: true })
  )
  boxFrame.position.set(cx, cy, cz)
  boundsGroup.add(boxFrame)

  // 2. 挂载坐标刻度文字
  const scaleRatio = Math.max(w, h, d) * 0.15
  const addLabel = (txt: string, x: number, y: number, z: number, color: string) => {
    const sp = makeTextSprite(txt, color)
    sp.position.set(x, y, z)
    sp.scale.set(scaleRatio, scaleRatio / 2, 1)
    boundsGroup!.add(sp)
  }

  addLabel(`Z: ${minZ}m`, minX, minY - scaleRatio * 0.3, minZ, '#1890ff')
  addLabel(`Z: ${maxZ}m`, minX, minY - scaleRatio * 0.3, maxZ, '#1890ff')

  addLabel(`X: ${minX}m`, minX, minY - scaleRatio * 0.3, minZ, '#ff4d4f')
  addLabel(`X: ${maxX}m`, maxX, minY - scaleRatio * 0.3, minZ, '#ff4d4f')

  addLabel(`Y: ${minY}m`, minX - scaleRatio * 0.3, minY, minZ, '#52c41a')
  addLabel(`Y: ${maxY}m`, minX - scaleRatio * 0.3, maxY, minZ, '#52c41a')

  mainScene.add(boundsGroup)

  // 自动调整相机视野
  controls.target.set(cx, cy, cz)
  const maxDim = Math.max(w, h, d)
  mainCamera.position.set(cx + maxDim * 1.5, cy + maxDim * 1.2, cz + maxDim * 1.5)
}

const createThickAxesHUD = () => {
  const group = new THREE.Group()
  const radius = 0.08
  const len = 2.0
  const cylinderGeo = new THREE.CylinderGeometry(radius, radius, len, 12)
  cylinderGeo.translate(0, len / 2, 0)

  const axisX = new THREE.Mesh(cylinderGeo, new THREE.MeshBasicMaterial({ color: 0xff0000 }))
  axisX.rotation.z = -Math.PI / 2
  const labelX = makeTextSprite('X', '#ff0000', 60)
  labelX.position.set(len + 0.5, 0, 0)
  labelX.scale.set(1.5, 1.5, 1.5)

  const axisY = new THREE.Mesh(cylinderGeo, new THREE.MeshBasicMaterial({ color: 0x00ff00 }))
  const labelY = makeTextSprite('Y', '#00ff00', 60)
  labelY.position.set(0, len + 0.5, 0)
  labelY.scale.set(1.5, 1.5, 1.5)

  const axisZ = new THREE.Mesh(cylinderGeo, new THREE.MeshBasicMaterial({ color: 0x0000ff }))
  axisZ.rotation.x = Math.PI / 2
  const labelZ = makeTextSprite('Z', '#0000ff', 60)
  labelZ.position.set(0, 0, len + 0.5)
  labelZ.scale.set(1.5, 1.5, 1.5)

  const originSphere = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.5, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0x333333 })
  )
  group.add(axisX, labelX, axisY, labelY, axisZ, labelZ, originSphere)
  return group
}

const initThreeJS = () => {
  if (!canvasRef.value || renderer) return
  renderer = new THREE.WebGLRenderer({ canvas: canvasRef.value, antialias: true, alpha: true })
  renderer.setSize(canvasRef.value.clientWidth, canvasRef.value.clientHeight)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.autoClear = false

  mainScene = new THREE.Scene()
  // 🌟 将背景设置为纯粹的明亮白底
  mainScene.background = new THREE.Color('#fdfdfd')

  mainCamera = new THREE.PerspectiveCamera(
    45,
    canvasRef.value.clientWidth / canvasRef.value.clientHeight,
    1,
    10000
  )

  controls = new TrackballControls(mainCamera, renderer.domElement)
  controls.rotateSpeed = 4.0
  controls.zoomSpeed = 1.2
  controls.panSpeed = 0.8

  // 增强白底下的灯光阴影
  mainScene.add(new THREE.AmbientLight(0xffffff, 0.8))
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.5)
  dirLight.position.set(100, 200, 50)
  mainScene.add(dirLight)

  hudScene = new THREE.Scene()
  hudCamera = new THREE.PerspectiveCamera(50, 1, 0.1, 100)
  hudScene.add(createThickAxesHUD())

  animate()
  window.addEventListener('resize', onWindowResize)
}

const rebuildMesh = () => {
  if (!mainScene || rawVoxelData.length === 0) return
  if (instancedMesh) {
    mainScene.remove(instancedMesh)
    instancedMesh.geometry.dispose()
    ;(instancedMesh.material as THREE.Material).dispose()
  }

  let minRes = Infinity,
    maxRes = -Infinity
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity,
    minZ = Infinity,
    maxZ = -Infinity

  rawVoxelData.forEach((p) => {
    if (p[0] < minX) minX = p[0]
    if (p[0] > maxX) maxX = p[0]
    if (p[1] < minY) minY = p[1]
    if (p[1] > maxY) maxY = p[1]
    if (p[2] < minZ) minZ = p[2]
    if (p[2] > maxZ) maxZ = p[2]
    if (p[3] < minRes) minRes = p[3]
    if (p[3] > maxRes) maxRes = p[3]
  })

  globalMinRes.value = minRes
  globalMaxRes.value = maxRes

  buildBoundingBoxAndScales(minX, maxX, minY, maxY, minZ, maxZ)

  const geometry = new THREE.BoxGeometry(cubeSize.value, cubeSize.value, cubeSize.value)
  const material = new THREE.MeshPhongMaterial({
    transparent: true,
    opacity: opacity.value,
    depthWrite: opacity.value === 1.0
  })
  instancedMesh = new THREE.InstancedMesh(geometry, material, rawVoxelData.length)

  const dummy = new THREE.Object3D()
  const color = new THREE.Color()

  rawVoxelData.forEach((point, index) => {
    dummy.position.set(point[0], point[1], point[2])
    dummy.updateMatrix()
    instancedMesh!.setMatrixAt(index, dummy.matrix)
    color.set(getJetColor(point[3], minRes, maxRes))
    instancedMesh!.setColorAt(index, color)
  })

  instancedMesh.instanceMatrix.needsUpdate = true
  if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true
  mainScene.add(instancedMesh)
}

const getJetColor = (value: number, min: number, max: number) => {
  let v = (value - min) / (max - min + 1e-8)
  v = Math.max(0, Math.min(1, v))
  let r = Math.max(0, Math.min(1, 1.5 - Math.abs(1 - 4 * (v - 0.5))))
  let g = Math.max(0, Math.min(1, 1.5 - Math.abs(1 - 4 * (v - 0.25))))
  let b = Math.max(0, Math.min(1, 1.5 - Math.abs(1 - 4 * v)))
  return new THREE.Color(r, g, b)
}

const onMouseMove = (event: MouseEvent) => {
  if (!canvasRef.value || !instancedMesh) return
  const rect = canvasRef.value.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, mainCamera)
  const intersects = raycaster.intersectObject(instancedMesh)

  if (intersects.length > 0) {
    const instanceId = intersects[0].instanceId
    if (instanceId !== undefined) {
      const data = rawVoxelData[instanceId]
      hoverData.value = { x: data[0], y: data[1], z: data[2], res: data[3] }
      tooltipVisible.value = true
      tooltipX.value = event.clientX + 20
      tooltipY.value = event.clientY + 20
    }
  } else {
    tooltipVisible.value = false
  }
}

const animate = () => {
  requestAnimationFrame(animate)
  if (!renderer) return

  controls.update()
  const width = canvasRef.value!.clientWidth
  const height = canvasRef.value!.clientHeight

  renderer.setViewport(0, 0, width, height)
  renderer.setScissor(0, 0, width, height)
  renderer.setScissorTest(false)
  renderer.clear()
  renderer.render(mainScene, mainCamera)

  const hudSize = 160
  renderer.setViewport(20, 20, hudSize, hudSize)
  renderer.setScissor(20, 20, hudSize, hudSize)
  renderer.setScissorTest(true)

  const dir = mainCamera.position.clone().sub(controls.target).normalize()
  hudCamera.position.copy(dir.multiplyScalar(7))
  hudCamera.up.copy(mainCamera.up)
  hudCamera.lookAt(0, 0, 0)

  renderer.clearDepth()
  renderer.render(hudScene, hudCamera)
}

const onWindowResize = () => {
  if (!canvasRef.value || !mainCamera || !renderer) return
  const w = canvasRef.value.clientWidth
  const h = canvasRef.value.clientHeight
  mainCamera.aspect = w / h
  mainCamera.updateProjectionMatrix()
  renderer.setSize(w, h, false)
  if (controls) controls.handleResize()
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  if (renderer) renderer.dispose()
})
</script>

<style scoped>
.threed-container {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}
.control-panel {
  padding: 25px;
  background: #f5f7fa;
  border-radius: 6px;
  border-left: 5px solid #67c23a;
  margin-bottom: 20px;
}
.header-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.empty-state {
  padding: 80px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
}
.file-inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
  background: #fff;
  padding: 15px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}
.file-row {
  display: flex;
  align-items: center;
}
.label {
  font-weight: bold;
  width: 220px;
  font-size: 14px;
}
.x-color {
  color: #ff4d4f;
}
.y-color {
  color: #52c41a;
}
.z-color {
  color: #1890ff;
}

.primary-btn {
  padding: 12px 24px;
  font-size: 15px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  width: 100%;
  transition: 0.3s;
}
.primary-btn:hover {
  background: #66b1ff;
}
.primary-btn:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.render-controls {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px dashed #dcdfe6;
  display: flex;
  gap: 40px;
}
.control-item {
  flex: 1;
}
.slider-label {
  font-size: 14px;
  font-weight: bold;
  color: #606266;
  display: block;
  margin-bottom: 5px;
}

.render-panel {
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #ebeef5;
}
.toolbar {
  padding: 12px;
  background: #f0f2f5;
  color: #333;
  font-size: 13px;
  border-bottom: 1px solid #dcdfe6;
}

/* 切换为明亮的白底 */
.canvas-wrapper {
  position: relative;
  width: 100%;
  height: 750px;
  background: #fdfdfd;
}
.three-canvas {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

/* === 明亮模式下的色阶图例 === */
.colorbar-hud {
  position: absolute;
  bottom: 30px;
  right: 30px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #dcdfe6;
  padding: 15px;
  border-radius: 8px;
  color: #333;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  pointer-events: none;
}
.cb-title {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 10px;
  color: #606266;
}
.cb-scale {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.cb-val {
  font-size: 12px;
  font-weight: bold;
  margin: 5px 0;
}
.cb-gradient {
  width: 24px;
  height: 180px;
  border-radius: 4px;
  border: 1px solid #999;
  background: linear-gradient(
    to top,
    #00007f 0%,
    #0000ff 12.5%,
    #00ffff 37.5%,
    #00ff00 50%,
    #ffff00 62.5%,
    #ff0000 87.5%,
    #7f0000 100%
  );
}

/* === 明亮模式下的悬浮探针 === */
.hover-tooltip {
  position: fixed;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #409eff;
  color: #333;
  padding: 12px 15px;
  border-radius: 6px;
  font-size: 13px;
  pointer-events: none;
  z-index: 1000;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(4px);
  min-width: 160px;
}
.tt-title {
  color: #409eff;
  font-weight: bold;
  margin-bottom: 8px;
  font-size: 14px;
}
.tt-val {
  float: right;
  color: #303133;
  font-family: monospace;
  font-size: 14px;
}
.tt-val.res {
  color: #f56c6c;
  font-weight: bold;
  font-size: 15px;
}
.tt-divider {
  border: 0;
  border-top: 1px dashed #dcdfe6;
  margin: 8px 0;
}
</style>
