// API 层统一出口：所有域模块的 HTTP 调用都经由本文件复用 lib/request.ts 的 axios 封装
// （401 统一跳登录、错误信息归一化为 Error message）。
export { httpRequest, request } from "@/lib/request";
