// 跨域共享的基础类型别名：被多个域模块（models / image-tasks / auth-keys 等）与页面共同引用。

/** 上游模型 ID（如 gpt-image-2、codex-gpt-image-2、plus-gpt-image-2 等） */
export type ImageModel = string;

/** 登录用户的角色：admin 可访问全部管理页，user 仅能用对话/生图 */
export type AuthRole = "admin" | "user";
