import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { config } from "../config.js";
import mime from "mime-types";
import crypto from "crypto";

export const s3 = new S3Client({
  endpoint: config.spaces.endpoint,
  region: config.spaces.region,
  credentials: {
    accessKeyId: config.spaces.key,
    secretAccessKey: config.spaces.secret
  }
});

export function buildCdnUrl(spaceKey: string): string {
  return `${config.spaces.cdnBase.replace(/\/$/, "")}/${spaceKey}`;
}

export function sha256(buffer: Buffer): string {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

export async function uploadBuffer(params: {
  key: string;
  buffer: Buffer;
  contentType?: string;
}) {
  const contentType =
    params.contentType ||
    (mime.lookup(params.key) || "application/octet-stream").toString();

  await s3.send(
    new PutObjectCommand({
      Bucket: config.spaces.bucket,
      Key: params.key,
      Body: params.buffer,
      ACL: "public-read",
      ContentType: contentType
    })
  );

  return {
    spaceKey: params.key,
    cdnUrl: buildCdnUrl(params.key),
    fileHash: sha256(params.buffer),
    mimeType: contentType
  };
}
