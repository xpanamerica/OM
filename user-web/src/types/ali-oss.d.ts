declare module "ali-oss" {
  type MultipartProgress = (p: number, checkpoint: unknown, res: unknown) => void;

  export default class OSS {
    constructor(options: Record<string, unknown>);
    multipartUpload(
      name: string,
      file: File | Blob,
      options?: { progress?: MultipartProgress; parallel?: number; partSize?: number },
    ): Promise<unknown>;
  }
}
