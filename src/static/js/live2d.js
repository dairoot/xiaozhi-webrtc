/**
 * Live2D 管理器
 * 负责 Live2D 模型的初始化、嘴部动画控制等功能
 */
class Live2DManager {
    constructor() {
        this.live2dApp = null;
        this.live2dModel = null;
        this.canvas = null;
        this.isTalking = false;
        this.mouthAnimationId = null;
        this.mouthParam = 'ParamMouthOpenY';
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        // 单/双击判定配置与状态
        this._lastClickTime = 0;
        this._lastClickPos = { x: 0, y: 0 };
        this._singleClickTimer = null;
        this._doubleClickMs = 280; // 双击时间阈值(ms)
        this._doubleClickDist = 16; // 双击允许的最大位移(px)
        // 滑动判定
        this._pointerDown = false;
        this._downPos = { x: 0, y: 0 };
        this._downTime = 0;
        this._downArea = 'Body';
        this._movedBeyondClick = false;
        this._swipeMinDist = 24; // 触发滑动的最小距离
    }

    /**
     * 初始化 Live2D
     */
    async initializeLive2D() {
        try {
            const canvas = document.getElementById('live2d-stage');
            this.canvas = canvas;

            // 供内部使用
            window.PIXI = PIXI;

            this.live2dApp = new PIXI.Application({
                view: canvas,
                height: window.innerHeight,
                width: window.innerWidth,
                resolution: window.devicePixelRatio,
                autoDensity: true,
                antialias: true,
                backgroundAlpha: 0,
            });

            // 加载 Live2D 模型
            this.live2dModel = await PIXI.live2d.Live2DModel.from('static/hiyori_pro_zh/runtime/hiyori_pro_t11.model3.json');
            this.live2dApp.stage.addChild(this.live2dModel);
            this.live2dModel.scale.set(0.35);
            this.live2dModel.x = (window.innerWidth - this.live2dModel.width) * 0.5;
            this.live2dModel.y = -50;

            // 启用交互并监听点击命中（头部/身体等）

            this.live2dModel.interactive = true;


            this.live2dModel.on('doublehit', (args) => {
                const area = Array.isArray(args) ? args[0] : args;
                console.log('doublehit', area);
                const app = window.chatApp;
                const payload = JSON.stringify({ type: 'live2d', event: 'doublehit', area });
                if (app && app.dataChannel && app.dataChannel.readyState === 'open') {
                    app.dataChannel.send(payload);
                } 

            });

            this.live2dModel.on('singlehit', (args) => {
                const area = Array.isArray(args) ? args[0] : args;
                console.log('singlehit', area);
                const app = window.chatApp;
                const payload = JSON.stringify({ type: 'live2d', event: 'singlehit', area });
                if (app && app.dataChannel && app.dataChannel.readyState === 'open') {
                    app.dataChannel.send(payload);
                }

            });

            this.live2dModel.on('swipe', (args) => {
                const area = Array.isArray(args) ? args[0] : args;
                const dir = Array.isArray(args) ? args[1] : undefined;
                console.log('swipe', area, dir);

                const app = window.chatApp;
                const payload = JSON.stringify({ type: 'live2d', event: 'swipe', area, dir });
                if (app && app.dataChannel && app.dataChannel.readyState === 'open') {
                    app.dataChannel.send(payload);
                } 

            });

            // 兜底：自定义"头部/身体"命中区域 + 单/双击/滑动区分
            this.live2dModel.on('pointerdown', (event) => {
                try {
                    const global = event.data.global;
                    const area = this._getAreaFromGlobal(global);
                    if (area === '') {
                        return;
                    }

                    // 记录按下状态用于滑动判定
                    this._pointerDown = true;
                    this._downPos = { x: global.x, y: global.y };
                    this._downTime = performance.now();
                    this._downArea = area;
                    this._movedBeyondClick = false;

                    // 按下脸部时切换为"捏住"手势
                    this._updateCursor(global);

                    const now = performance.now();
                    const dt = now - (this._lastClickTime || 0);
                    const dx = global.x - (this._lastClickPos?.x || 0);
                    const dy = global.y - (this._lastClickPos?.y || 0);
                    const dist = Math.hypot(dx, dy);

                    // 命中确认：仅当点击在模型上时做单/双击判断
                    if (this._lastClickTime && dt <= this._doubleClickMs && dist <= this._doubleClickDist) {
                        // 判定为双击：取消待触发的单击事件
                        if (this._singleClickTimer) {
                            clearTimeout(this._singleClickTimer);
                            this._singleClickTimer = null;
                        }
                        if (typeof this.live2dModel.emit === 'function') {
                            this.live2dModel.emit('doublehit', [area]);
                        }
                        this._lastClickTime = 0;
                        this._pointerDown = false; // 双击完成，重置状态
                        return;
                    }

                    // 可能是单击：记录并延迟确认
                    this._lastClickTime = now;
                    this._lastClickPos = { x: global.x, y: global.y };
                    if (this._singleClickTimer) {
                        clearTimeout(this._singleClickTimer);
                        this._singleClickTimer = null;
                    }
                    this._singleClickTimer = setTimeout(() => {
                        // 若在等待期间发生了移动超过阈值，则不再当作单击
                        if (!this._movedBeyondClick && typeof this.live2dModel.emit === 'function') {
                            this.live2dModel.emit('singlehit', [area]);
                        }
                        this._singleClickTimer = null;
                        this._lastClickTime = 0;
                    }, this._doubleClickMs);
                } catch (e) {
                    // 忽略自定义命中判断中的异常，避免影响主流程
                }
            });

            // 指针移动：用于判定是否从"点击"升级为"滑动"
            this.live2dModel.on('pointermove', (event) => {
                try {
                    const global = event.data.global;
                    if (!this._pointerDown) {
                        // 悬停时根据所在区域更新光标（脸部显示"捏脸"手势）
                        this._updateCursor(global);
                        return;
                    }
                    const dx = global.x - this._downPos.x;
                    const dy = global.y - this._downPos.y;
                    const dist = Math.hypot(dx, dy);
                    
                    // 使用 _doubleClickDist 作为点击/滑动的判定阈值
                    if (dist > this._doubleClickDist) {
                        this._movedBeyondClick = true;
                        // 若已超出点击阈值，取消可能的单击触发
                        if (this._singleClickTimer) {
                            clearTimeout(this._singleClickTimer);
                            this._singleClickTimer = null;
                        }
                        this._lastClickTime = 0;
                    }
                } catch (e) {
                    // 忽略移动判定中的异常
                }
            });

            // 指针抬起：确认是否为滑动
            const handlePointerUp = (event) => {
                try {
                    if (!this._pointerDown) return;
                    const global = (event && event.data && event.data.global) ? event.data.global : { x: this._downPos.x, y: this._downPos.y };
                    const dx = global.x - this._downPos.x;
                    const dy = global.y - this._downPos.y;
                    const dist = Math.hypot(dx, dy);

                    // 滑动：超过滑动最小距离则触发 swipe 事件（携带方向与区域）
                    if (this._movedBeyondClick && dist >= this._swipeMinDist) {
                        if (typeof this.live2dModel.emit === 'function') {
                            const dir = Math.abs(dx) >= Math.abs(dy)
                                ? (dx > 0 ? 'right' : 'left')
                                : (dy > 0 ? 'down' : 'up');
                            this.live2dModel.emit('swipe', [this._downArea, dir]);
                        }
                        // 终止：不再让单击/双击触发
                        if (this._singleClickTimer) {
                            clearTimeout(this._singleClickTimer);
                            this._singleClickTimer = null;
                        }
                        this._lastClickTime = 0;
                    }
                } catch (e) {
                    // 忽略抬起判定中的异常
                }
                finally {
                    this._pointerDown = false;
                    this._movedBeyondClick = false;
                    // 松手后恢复为悬停状态的光标
                    const g = (event && event.data && event.data.global) ? event.data.global : null;
                    this._updateCursor(g);
                }
            };

            this.live2dModel.on('pointerup', handlePointerUp);
            this.live2dModel.on('pointerupoutside', handlePointerUp);

            // 指针移出模型时恢复默认光标
            this.live2dModel.on('pointerout', () => {
                if (!this._pointerDown && this.canvas) {
                    this.canvas.style.cursor = 'default';
                }
            });
            
                
        } catch (err) {
            console.error('加载 Live2D 模型失败:', err);
        }
    }

    /**
     * 根据全局坐标判定命中区域（Head/Face/Body），未命中返回 ''
     * @param {{x:number, y:number}} global
     * @returns {string}
     */
    _getAreaFromGlobal(global) {
        if (!this.live2dModel || !global) return '';
        const bounds = this.live2dModel.getBounds();
        // 仅在落在模型可见范围内时判定
        if (!bounds || !bounds.contains(global.x, global.y)) return '';

        const relX = (global.x - bounds.x) / (bounds.width || 1);
        const relY = (global.y - bounds.y) / (bounds.height || 1);
        // 经验阈值：模型可见矩形上部按高度划分头部/脸部
        if (relX >= 0.4 && relX <= 0.6) {
            if (relY <= 0.15) return 'Head';
            if (relY <= 0.23) return 'Face';
            return 'Body';
        }
        return '';
    }

    /**
     * 根据当前指针位置更新画布光标：
     * 悬停在模型(头部/脸部/身体)显示"捏一捏"手势(grab)，按住时为"捏住"(grabbing)
     * @param {{x:number, y:number}|null} global
     */
    _updateCursor(global) {
        if (!this.canvas) return;
        const overModel = this._getAreaFromGlobal(global) !== '';
        const grabbedModel = this._pointerDown && this._downArea !== '';

        let cursor = 'default';
        if (grabbedModel) {
            cursor = 'grabbing';
        } else if (overModel) {
            cursor = this._pointerDown ? 'grabbing' : 'grab';
        }
        this.canvas.style.cursor = cursor;
    }

    /**
     * 初始化音频分析器
     * @param {MediaStream} remoteStream - 远程音频流
     */
    initializeAudioAnalyzer(remoteStream) {
        try {
            // 创建音频上下文和分析器
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);

            // 获取remoteVideo的音频轨道
            if (remoteStream) {
                const audioTracks = remoteStream.getAudioTracks();
                if (audioTracks.length > 0) {
                    const source = this.audioContext.createMediaStreamSource(remoteStream);
                    source.connect(this.analyser);
                    // console.log('音频分析器初始化成功');
                }
            }
        } catch (error) {
            console.error('初始化音频分析器失败:', error);
        }
    }

    /**
     * 嘴部动画循环
     */
    animateMouth() {
        if (!this.isTalking) return;
        if (!this.live2dModel) return;
        const internal = this.live2dModel && this.live2dModel.internalModel;
        if (internal && internal.coreModel) {
            const coreModel = internal.coreModel;

            // 获取音频分贝值
            let mouthValue = 0;
            if (this.analyser && this.dataArray) {
                this.analyser.getByteFrequencyData(this.dataArray);
                const average = this.dataArray.reduce((a, b) => a + b) / this.dataArray.length;
                // 将0-255的值转换为0-1的范围，并应用一些平滑处理
                mouthValue =  Math.pow(Math.min(1, (average / 255) * 3), 2);
                // console.log("mouthValue", mouthValue, average)
            }
            // console.log("mouthValue", mouthValue)
            coreModel.setParameterValueById(this.mouthParam, mouthValue);
            coreModel.update();
        }
        this.mouthAnimationId = requestAnimationFrame(() => this.animateMouth());
    }

    /**
     * 开始说话动画
     * @param {MediaStream} remoteStream - 远程音频流
     */
    startTalking(remoteStream) {
        if (this.isTalking || !this.live2dModel) return;

        // 确保音频分析器已初始化
        if (!this.analyser && remoteStream) {
            this.initializeAudioAnalyzer(remoteStream);
        }

        this.isTalking = true;
        this.animateMouth();
    }

    /**
     * 停止说话动画
     */
    stopTalking() {
        this.isTalking = false;
        if (this.mouthAnimationId) {
            cancelAnimationFrame(this.mouthAnimationId);
            this.mouthAnimationId = null;
        }
        if (!this.live2dModel) return;
        const internal = this.live2dModel && this.live2dModel.internalModel;
        if (internal && internal.coreModel) {
            const coreModel = internal.coreModel;
            coreModel.setParameterValueById(this.mouthParam, 0);
            coreModel.update();
        }
    }

    /**
     * 触发模型动作（Motion）
     * @param {string} name - 动作分组名称，如 'TapBody'、'FlickUp'、'Idle' 等
     */
    motion(name) {
        try {
            if (!this.live2dModel) return;
            console.log("motion:", name);
            this.live2dModel.motion(name);
        } catch (error) {
            console.error('触发动作失败:', error);
        }
    }

    /**
     * 清理资源
     */
    destroy() {
        this.stopTalking();
        
        // 清理音频分析器
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        this.analyser = null;
        this.dataArray = null;

        // 清理 Live2D 应用
        if (this.live2dApp) {
            this.live2dApp.destroy(true);
            this.live2dApp = null;
        }
        this.live2dModel = null;
    }
}

// 导出全局实例
window.Live2DManager = Live2DManager;
