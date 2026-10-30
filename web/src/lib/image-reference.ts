/**
 * 参考图读取与转换：File ↔ dataUrl ↔ 结果图之间的互相转换。
 * 供图片页「继续编辑」「复用提示词配置」等把历史图片重新作为参考图的链路使用。
 */

import type { StoredImage, StoredReferenceImage } from "@/store/image-conversations";

/** 把 File 读取为 base64 dataUrl（FileReader 的 Promise 包装） */
export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取参考图失败"));
    reader.readAsDataURL(file);
  });
}

/** 把 base64 dataUrl 还原为 File 对象 */
export function dataUrlToFile(dataUrl: string, fileName: string, mimeType?: string): File {
  const [header, content] = dataUrl.split(",", 2);
  const matchedMimeType = header.match(/data:(.*?);base64/)?.[1];
  const binary = atob(content || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new File([bytes], fileName, { type: mimeType || matchedMimeType || "image/png" });
}

/** 从 URL 拉取图片并转为 File（用于结果图只有 url、没有内嵌 base64 的场景） */
export async function fetchImageAsFile(url: string, fileName: string): Promise<File> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("读取结果图失败");
  }
  const blob = await response.blob();
  return new File([blob], fileName, { type: blob.type || "image/png" });
}

/** 有内嵌 base64 的结果图直接构造参考图，否则返回 null 走 url 拉取路径 */
function buildReferenceImageFromResult(image: StoredImage, fileName: string): StoredReferenceImage | null {
  if (!image.b64_json) {
    return null;
  }
  return {
    name: fileName,
    type: "image/png",
    dataUrl: `data:image/png;base64,${image.b64_json}`,
  };
}

/**
 * 把一张已存储的结果图转换为「继续编辑」可用的参考图：
 * 返回 referenceImage（预览用 dataUrl）与 file（提交生图用 File）。
 * 优先用内嵌 base64，其次从 url 拉取；两者都不可用时返回 null。
 */
export async function buildReferenceImageFromStoredImage(
  image: StoredImage,
  fileName: string,
): Promise<{ referenceImage: StoredReferenceImage; file: File } | null> {
  const direct = buildReferenceImageFromResult(image, fileName);
  if (direct) {
    return {
      referenceImage: direct,
      file: dataUrlToFile(direct.dataUrl, direct.name, direct.type),
    };
  }

  if (!image.url) {
    return null;
  }
  const file = await fetchImageAsFile(image.url, fileName);
  return {
    referenceImage: {
      name: file.name,
      type: file.type || "image/png",
      dataUrl: await readFileAsDataUrl(file),
    },
    file,
  };
}
