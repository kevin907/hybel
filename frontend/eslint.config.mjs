import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // Enforce explicit return types are not required (too noisy for React components)
      "@typescript-eslint/explicit-function-return-type": "off",

      // Allow unused vars prefixed with _ (common pattern for destructuring)
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],

      // Warn on console.log in production code (allow warn/error)
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
  {
    ignores: [
      ".next/",
      "out/",
      "node_modules/",
      "coverage/",
      "jest.config.ts",
      "next-env.d.ts",
      "postcss.config.mjs",
    ],
  },
];

export default eslintConfig;
