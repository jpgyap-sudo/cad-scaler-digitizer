import { prisma } from "../db.js";
import { slugify } from "../utils/slug.js";
import { AssetType } from "@prisma/client";

export async function upsertProductReference(input: {
  manufacturer: string;
  productName: string;
  sourceUrl?: string;
  category?: string;
  subcategory?: string;
  metadata?: unknown;
}) {
  const slug = slugify(`${input.manufacturer}-${input.productName}`);

  return prisma.productReference.upsert({
    where: { id: slug },
    update: {
      manufacturer: input.manufacturer,
      productName: input.productName,
      sourceUrl: input.sourceUrl,
      category: input.category,
      subcategory: input.subcategory,
      metadata: input.metadata as any
    },
    create: {
      id: slug,
      slug,
      manufacturer: input.manufacturer,
      productName: input.productName,
      sourceUrl: input.sourceUrl,
      category: input.category,
      subcategory: input.subcategory,
      metadata: input.metadata as any
    }
  });
}

export async function createAsset(input: {
  productReferenceId: string;
  assetType: AssetType;
  fileName: string;
  mimeType?: string;
  spaceKey: string;
  cdnUrl: string;
  fileHash?: string;
  metadata?: unknown;
}) {
  return prisma.referenceAsset.create({
    data: {
      productReferenceId: input.productReferenceId,
      assetType: input.assetType,
      fileName: input.fileName,
      mimeType: input.mimeType,
      spaceKey: input.spaceKey,
      cdnUrl: input.cdnUrl,
      fileHash: input.fileHash,
      metadata: input.metadata as any
    }
  });
}
