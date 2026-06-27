import swaggerJsdoc from "swagger-jsdoc";

const options: swaggerJsdoc.Options = {
  definition: {
    openapi: "3.0.3",
    info: {
      title: "CAD Reference Library API",
      version: "1.0.0",
      description: `
API for managing CAD reference product libraries.
- Product references (CRUD)
- Asset uploads to DigitalOcean Spaces
- DXF parsing and geometry indexing in Qdrant
- Crawl job management for automatic catalog ingestion
      `.trim(),
    },
    servers: [
      { url: "http://localhost:4000", description: "Local dev" },
    ],
    components: {
      securitySchemes: {
        ApiKeyAuth: {
          type: "apiKey",
          in: "header",
          name: "x-api-key",
        },
      },
    },
    security: [{ ApiKeyAuth: [] }],
  },
  apis: ["./src/routes/*.ts"],
};

export const openapiSpec = swaggerJsdoc(options);
