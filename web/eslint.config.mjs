import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';
import prettier from 'eslint-config-prettier/flat';

const eslintConfig = [
    ...nextCoreWebVitals,
    ...nextTypescript,
    prettier,
    {
        rules: {
            // 未使用变量降级为告警：孤儿 import / 死变量仍可见，但不阻塞构建（审查 R2-M5/R3-L10）
            '@typescript-eslint/no-unused-vars': 'warn',
            // strict 全开、禁止 any（CLAUDE.md 前端规范；当前全仓 0 处 any）
            '@typescript-eslint/no-explicit-any': 'error',
        },
    },
];

export default eslintConfig;
