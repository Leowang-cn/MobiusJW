// ==UserScript==
// @name         提取菁优网题目
// @namespace    http://tampermonkey.net/
// @version      3.0
// @description  1）提取题目fieldset id;2)将题目片段渲染为PNG图片;3)支持将题目导入主程序
// @match        *://*/*
// @require      https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js
// @grant        none
// ==/UserScript==



(function() {
    console.log('脚本已注入');
    'use strict';

    const COPYRIGHT_TEXT = '声明：本试题解析著作权属菁优网所有，未经书面同意，不得复制发布。';
    const IMPORT_ENDPOINT = 'http://127.0.0.1:27777/import';
    const IMPORT_TOKEN = ''; // 从 MobiusJ 的 settings.json 中复制 token 到这里

    function createButton(text) {
        const btn = document.createElement('button');
        btn.textContent = text;
        btn.style.margin = '8px';
        btn.style.padding = '2px 8px';
        btn.style.fontSize = '14px';
        btn.style.cursor = 'pointer';
        btn.style.position = 'relative';
        btn.style.zIndex = 999;
        return btn;
    }

    function createCopyIdButton(fieldset) {
        const btn = createButton('复制ID');
        btn.addEventListener('click', async (e) => {
            // 阻止事件冒泡和默认行为，防止被全局copy监听检测
            e.stopPropagation();
            e.preventDefault();
            try {
                // 直接用Clipboard API复制，不触发copy事件
                await navigator.clipboard.writeText(fieldset.id);
                showTip('ID已复制到剪切板！');
            } catch (err) {
                showTip('复制ID失败');
            }
        });
        return btn;
    }

    function showTip(message) {
        const tip = document.createElement('div');
        tip.textContent = message;
        tip.style.position = 'fixed';
        tip.style.top = '50%';
        tip.style.left = '50%';
        tip.style.transform = 'translate(-50%, -50%)';
        tip.style.background = 'rgba(0,0,0,0.8)';
        tip.style.color = 'white';
        tip.style.padding = '10px 20px';
        tip.style.borderRadius = '5px';
        tip.style.zIndex = '10000';
        tip.style.fontSize = '14px';
        document.body.appendChild(tip);
        setTimeout(() => {
            if (tip.parentNode) {
                tip.parentNode.removeChild(tip);
            }
        }, 1000);
    }

    function waitForImages(question) {
        const imgs = question.querySelectorAll('img');
        return Promise.all(Array.from(imgs).map(img => {
            if (img.complete) return Promise.resolve();
            return new Promise(resolve => {
                img.onload = img.onerror = resolve;
            });
        }));
    }

    function canvasToBlob(canvas) {
        return new Promise((resolve, reject) => {
            canvas.toBlob(blob => {
                if (blob) {
                    resolve(blob);
                } else {
                    reject(new Error('生成图片失败'));
                }
            }, 'image/png');
        });
    }

    function blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    function runCleanup(cleanups) {
        for (let i = cleanups.length - 1; i >= 0; i -= 1) {
            try {
                cleanups[i]();
            } catch (e) {
                console.error('cleanup error', e);
            }
        }
    }

    function findKeyPointChildIndex(question) {
        const children = Array.from(question.children);
        return children.findIndex(child => child.textContent && child.textContent.includes('【考点】'));
    }

    async function renderQuestionToBlob(question, options = {}) {
        const cleanups = [];
        const {
            hideChildrenFromIndex
        } = options;

        const quizPutTags = Array.from(question.querySelectorAll('.quizPutTag'));
        quizPutTags.forEach(tag => {
            const previous = tag.innerHTML;
            if (previous === '***') return;
            cleanups.push(() => { tag.innerHTML = previous; });
            tag.innerHTML = '***';
        });

        const selectedLabels = Array.from(question.querySelectorAll('label.s'));
        selectedLabels.forEach(label => {
            cleanups.push(() => { label.classList.add('s'); });
            label.classList.remove('s');
        });

        const checkedElements = Array.from(question.querySelectorAll('[checked="checked"]'));
        checkedElements.forEach(element => {
            cleanups.push(() => { element.setAttribute('checked', 'checked'); });
            element.removeAttribute('checked');
        });

        const copyrightNodes = [];
        question.querySelectorAll('*').forEach(el => {
            if (el.textContent && el.textContent.includes(COPYRIGHT_TEXT)) {
                copyrightNodes.push(el);
            }
        });
        copyrightNodes.forEach(el => {
            const previous = el.style.display;
            cleanups.push(() => { el.style.display = previous; });
            el.style.display = 'none';
        });

        let hiddenChildren = [];
        if (typeof hideChildrenFromIndex === 'number' && hideChildrenFromIndex >= 0) {
            const children = Array.from(question.children);
            hiddenChildren = children.slice(hideChildrenFromIndex);
            hiddenChildren.forEach(child => {
                const previous = child.style.display;
                cleanups.push(() => { child.style.display = previous; });
                child.style.display = 'none';
            });
        }

        try {
            await waitForImages(question);
            const width = question.scrollWidth;
            const height = question.scrollHeight;
            const canvas = await window.html2canvas(question, { useCORS: true, scale: 2, width, height, logging: false });
            console.log('canvas.width:', canvas.width, 'canvas.height:', canvas.height);
            runCleanup(cleanups);
            return await canvasToBlob(canvas);
        } catch (error) {
            runCleanup(cleanups);
            throw error;
        }
    }

    async function captureQuestion(question, options = {}) {
        const blob = await renderQuestionToBlob(question, options);
        await navigator.clipboard.write([
            new window.ClipboardItem({ 'image/png': blob })
        ]);
        showTip('图片已复制到剪切板，可直接粘贴！');
    }

    async function importQuestion(question, options = {}) {
        const questionId = question.id || '';
        if (!questionId) {
            showTip('题目ID为空');
            return;
        }

        try {
            const blob = await renderQuestionToBlob(question, options);
            const imageBase64 = await blobToBase64(blob);
            const response = await fetch(IMPORT_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: questionId,
                    imageBase64,
                    token: IMPORT_TOKEN
                })
            });

            if (!response.ok) {
                const text = await response.text();
                console.warn('import failed:', response.status, text);
                showTip('导入失败');
                return;
            }
            showTip('已导入题库');
        } catch (e) {
            console.error('import error', e);
            showTip('客户端未启动或连接失败');
        }
    }

    function processQuestions() {
        if (typeof window.html2canvas !== 'function') return;
        const questions = document.querySelectorAll('.quesborder');
        questions.forEach(question => {
            if (question.tagName !== 'FIELDSET') return;
            if (question.dataset.imageButtonsAttached === '1') return;
            question.dataset.imageButtonsAttached = '1';

            // 新增：复制ID按钮
            const copyIdBtn = createCopyIdButton(question);

            const hasKeyPointSection = question.textContent && question.textContent.includes('【考点】');
            const keyPointChildIndex = hasKeyPointSection ? findKeyPointChildIndex(question) : -1;

            if (hasKeyPointSection) {
                const questionBtn = createButton('题目图片');
                const stemBtn = createButton('题干图片');
                const importBtn = createButton('导入题库');

                stemBtn.addEventListener('click', async () => {
                    try {
                        const targetIndex = (() => {
                            if (keyPointChildIndex >= 0) return keyPointChildIndex;
                            return findKeyPointChildIndex(question);
                        })();
                        const options = (typeof targetIndex === 'number' && targetIndex >= 0)
                            ? { hideChildrenFromIndex: targetIndex }
                            : {};
                        await captureQuestion(question, options);
                    } catch (e) {
                        alert('复制到剪切板失败：' + e);
                    }
                });

                questionBtn.addEventListener('click', async () => {
                    try {
                        await captureQuestion(question);
                    } catch (e) {
                        alert('复制到剪切板失败：' + e);
                    }
                });

                importBtn.addEventListener('click', async () => {
                    try {
                        await importQuestion(question);
                    } catch (e) {
                        alert('导入失败：' + e);
                    }
                });

                // 先插入复制ID按钮，再插入题目图片和题干图片按钮
                question.parentNode.insertBefore(copyIdBtn, question);
                question.parentNode.insertBefore(questionBtn, question);
                question.parentNode.insertBefore(stemBtn, question);
                question.parentNode.insertBefore(importBtn, question);
            } else {
                const btn = createButton('题目转图片');
                const importBtn = createButton('导入题库');
                btn.addEventListener('click', async () => {
                    try {
                        await captureQuestion(question);
                    } catch (e) {
                        alert('复制到剪切板失败：' + e);
                    }
                });
                importBtn.addEventListener('click', async () => {
                    try {
                        await importQuestion(question);
                    } catch (e) {
                        alert('导入失败：' + e);
                    }
                });
                // 先插入复制ID按钮，再插入题目转图片按钮
                question.parentNode.insertBefore(copyIdBtn, question);
                question.parentNode.insertBefore(btn, question);
                question.parentNode.insertBefore(importBtn, question);
            }
        });
    }

    // 定时检测，保证异步渲染的题目也能插入按钮
    setInterval(processQuestions, 1000);
})();
