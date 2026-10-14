import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/api/generated'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, prettier],
    languageOptions: { ecmaVersion: 2023, globals: globals.browser },
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
  {
    // MSW mocks are test-only and must never leak into production code.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/test/**', 'src/**/*.test.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: ['msw', 'msw/*', '@/test/*'] }],
    },
  },
)
