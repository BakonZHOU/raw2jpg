# [OPEN] 缩略图快速切换选中残留

## 症状
使用方向键快速切换当前预览时，会出现一串缩略图都保持放大/选中态，等界面更新后才逐步消失。

## 初始假设
1. current 状态更新时，旧缩略图没有被及时复位，导致多个按钮同时处于 `_is_current=True`。
2. `refresh_thumbnails()` 在高频切换时触发了过多的重建/刷新，旧按钮的动画来不及停止，视觉上形成残留。
3. `_animate_to_target()` 只根据 `current/hover` 决定目标缩放，但 current 切换时没有对旧按钮同步调用 `set_current(False)`。
4. 快速方向键触发时，`scroll_current_thumbnail_into_view()` 或延迟刷新合并了多次状态，导致短时间内多个按钮都处于放大过渡中。

## 证据收集计划
- 查看 current 切换入口是否显式复位旧按钮。
- 检查缩略图按钮是否在状态切换时中断旧动画。
- 检查 refresh 逻辑是否频繁重建按钮或批量更新。
- 如果必要，补充最小化 instrumentation 日志验证状态流转。