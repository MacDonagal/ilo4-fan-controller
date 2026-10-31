import type { NextApiRequest, NextApiResponse } from "next";

// Liveness endpoint for the Docker healthcheck: does NOT contact the iLO
const handler = (_req: NextApiRequest, res: NextApiResponse) => {
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ status: "ok" });
};

export default handler;
