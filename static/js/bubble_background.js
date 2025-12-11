// 气泡背景动画效果
class BubbleBackground {
    constructor(container = document.body) {
        this.container = container;
        this.bubbles = [];
        this.bubbleCount = 30; // 气泡数量
        this.init();
    }

    init() {
        // 设置容器背景为蓝紫色渐变
        this.container.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        this.container.style.margin = '0';
        this.container.style.padding = '0';
        this.container.style.overflowX = 'hidden';
        this.container.style.minHeight = '100vh';

        // 创建气泡
        for (let i = 0; i < this.bubbleCount; i++) {
            this.createBubble();
        }

        // 启动动画
        this.animate();
    }

    createBubble() {
        const bubble = document.createElement('div');

        // 随机大小
        const size = Math.random() * 100 + 100;

        // 随机位置
        const x = Math.random() * (this.container.offsetWidth - size);
        const y = Math.random() * (this.container.offsetHeight - size);

        // 随机颜色
        const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'];
        const color = colors[Math.floor(Math.random() * colors.length)];

        // 设置样式
        bubble.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            background-color: ${color};
            border-radius: 50%;
            left: ${x}px;
            top: ${y}px;
            opacity: 0.9;
            pointer-events: none;
            z-index: -1;
            filter: blur(3px);
            transition: width 2s ease, height 2s ease, filter 2s ease;
        `;

        // 添加到容器
        this.container.appendChild(bubble);

        // 保存气泡信息
        const bubbleData = {
            element: bubble,
            x: x,
            y: y,
            size: size,
            targetSize: size,
            vx: (Math.random() - 0.5) * 2,
            vy: (Math.random() - 0.5) * 2,
            color: color,
            sizeChangeTimer: null
        };

        this.bubbles.push(bubbleData);

        // 设置大小变化计时器
        bubbleData.sizeChangeTimer = this.setSizeChangeTimer(bubbleData);
    }

    setSizeChangeTimer(bubble) {
        // 随机设置1-5秒后改变大小
        const delay = Math.random() * 4000 + 1000;
        return setTimeout(() => {
            this.changeSize(bubble);
        }, delay);
    }

    animate() {
        for (let i = 0; i < this.bubbles.length; i++) {
            const bubble = this.bubbles[i];

            // 更新位置
            bubble.x += bubble.vx;
            bubble.y += bubble.vy;

            // 球与屏幕边缘碰撞检测
            if (bubble.x <= 0) {
                bubble.x = 0;
                bubble.vx *= -1;
            }
            if (bubble.x >= this.container.offsetWidth - bubble.size) {
                bubble.x = this.container.offsetWidth - bubble.size;
                bubble.vx *= -1;
            }
            if (bubble.y <= 0) {
                bubble.y = 0;
                bubble.vy *= -1;
            }
            if (bubble.y >= this.container.offsetHeight - bubble.size) {
                bubble.y = this.container.offsetHeight - bubble.size;
                bubble.vy *= -1;
            }

            // 球与球碰撞检测
            for (let j = i + 1; j < this.bubbles.length; j++) {
                const otherBubble = this.bubbles[j];
                this.checkBubbleCollision(bubble, otherBubble);
            }

            // 平滑调整大小
            if (Math.abs(bubble.size - bubble.targetSize) > 0.5) {
                const sizeDiff = bubble.targetSize - bubble.size;
                bubble.size += sizeDiff * 0.05;
                bubble.element.style.width = `${bubble.size}px`;
                bubble.element.style.height = `${bubble.size}px`;
            }

            // 更新样式
            bubble.element.style.left = `${bubble.x}px`;
            bubble.element.style.top = `${bubble.y}px`;
        }

        requestAnimationFrame(() => this.animate());
    }

    checkBubbleCollision(bubble1, bubble2) {
        // 计算两球中心距离
        const dx = (bubble1.x + bubble1.size / 2) - (bubble2.x + bubble2.size / 2);
        const dy = (bubble1.y + bubble1.size / 2) - (bubble2.y + bubble2.size / 2);
        const distance = Math.sqrt(dx * dx + dy * dy);

        // 检查是否碰撞
        if (distance < (bubble1.size / 2 + bubble2.size / 2)) {
            // 计算碰撞后速度
            const angle = Math.atan2(dy, dx);
            const sin = Math.sin(angle);
            const cos = Math.cos(angle);

            // 旋转气泡1的速度
            const vx1 = bubble1.vx * cos + bubble1.vy * sin;
            const vy1 = bubble1.vy * cos - bubble1.vx * sin;

            // 旋转气泡2的速度
            const vx2 = bubble2.vx * cos + bubble2.vy * sin;
            const vy2 = bubble2.vy * cos - bubble2.vx * sin;

            // 交换速度
            bubble1.vx = (vx2 * cos - vy1 * sin);
            bubble1.vy = (vy1 * cos + vx2 * sin);
            bubble2.vx = (vx1 * cos - vy2 * sin);
            bubble2.vy = (vy2 * cos + vx1 * sin);

            // 分离两球
            const overlap = (bubble1.size / 2 + bubble2.size / 2) - distance;
            const separationX = (overlap / 2) * cos;
            const separationY = (overlap / 2) * sin;

            bubble1.x += separationX;
            bubble1.y += separationY;
            bubble2.x -= separationX;
            bubble2.y -= separationY;

            // 碰撞时随机改变大小
            this.changeSize(bubble1);
            this.changeSize(bubble2);
        }
    }

    changeSize(bubble) {
        // 清除之前的计时器
        clearTimeout(bubble.sizeChangeTimer);

        // 随机选择变大或变小，大小范围20-120px
        const minSize = 20;
        const maxSize = 120;
        const currentSize = bubble.size;

        if (Math.random() > 0.5) {
            // 变大
            bubble.targetSize = Math.min(maxSize, currentSize + Math.random() * 20 + 10);
        } else {
            // 变小
            bubble.targetSize = Math.max(minSize, currentSize - Math.random() * 20 - 10);
        }

        // 重新设置计时器
        bubble.sizeChangeTimer = this.setSizeChangeTimer(bubble);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 将容器设置为body，确保全屏覆盖
    new BubbleBackground();
});