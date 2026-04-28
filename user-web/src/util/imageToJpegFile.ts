/** 将常见图片格式转为 JPEG ``File``（后端封面接口仅收 JPEG）。 */
export async function imageFileToJpegFile(f: File, name = "cover.jpg"): Promise<File> {
  if (f.type === "image/jpeg") return f;
  return new Promise((resolve, reject) => {
    const img = new Image();
    const u = URL.createObjectURL(f);
    img.onload = () => {
      URL.revokeObjectURL(u);
      try {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth || 640;
        canvas.height = img.naturalHeight || 360;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("无法处理图片"));
          return;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("导出 JPEG 失败"));
              return;
            }
            const base = name.replace(/\.[^.]+$/, "");
            resolve(new File([blob], `${base}.jpg`, { type: "image/jpeg" }));
          },
          "image/jpeg",
          0.92,
        );
      } catch (e) {
        reject(e);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(u);
      reject(new Error("无法读取图片"));
    };
    img.src = u;
  });
}
