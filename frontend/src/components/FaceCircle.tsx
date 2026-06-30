import { useQuery } from "@tanstack/react-query";
import { getPhotoFaces } from "../api/gallery";
import { apiFetchBlob } from "../api/client";
import type { Cluster, Photo } from "../types";

const CIRCLE_SIZE = 56;
const WEB_MAX_PX = 2000;

interface Props {
  cluster: Cluster;
  representativePhoto: Photo | undefined;
  isActive: boolean;
  onClick: () => void;
}

export function FaceCircle({
  cluster,
  representativePhoto,
  isActive,
  onClick,
}: Props) {
  const { data: blobUrl } = useQuery({
    queryKey: ["face-photo-blob", cluster.representative_photo_id],
    queryFn: () =>
      apiFetchBlob(`/me/photos/${cluster.representative_photo_id}/data`),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const { data: faces } = useQuery({
    queryKey: ["photo-faces", cluster.representative_photo_id],
    queryFn: () => getPhotoFaces(cluster.representative_photo_id),
    staleTime: Infinity, // face bboxes never change
  });

  const firstFace =
    faces?.find((f) => f.cluster_id === cluster.cluster_id) ?? faces?.[0];

  // Bboxes are in web-res coordinate space; compute web-res dimensions to match.
  const webW = representativePhoto?.width
    ? Math.round(
        representativePhoto.width *
          Math.min(
            1,
            WEB_MAX_PX /
              Math.max(
                representativePhoto.width,
                representativePhoto.height ?? 1,
              ),
          ),
      )
    : null;
  const webH = representativePhoto?.height
    ? Math.round(
        representativePhoto.height *
          Math.min(
            1,
            WEB_MAX_PX /
              Math.max(
                representativePhoto.width ?? 1,
                representativePhoto.height,
              ),
          ),
      )
    : null;

  // Use background-image crop instead of absolute-positioned <img> to avoid
  // browser quirks with position:absolute on img elements inside small containers.
  const bgCrop = (() => {
    const f = firstFace;
    if (
      !f ||
      f.bbox_x == null ||
      f.bbox_y == null ||
      f.bbox_w == null ||
      f.bbox_h == null ||
      !webW ||
      !webH
    )
      return null;
    const pad = f.bbox_w * 0.5;
    const cropX = Math.max(0, f.bbox_x - pad);
    const cropY = Math.max(0, f.bbox_y - pad);
    const cropW = Math.min(webW - cropX, f.bbox_w + 2 * pad);
    const cropH = Math.min(webH - cropY, f.bbox_h + 2 * pad);
    const scale = CIRCLE_SIZE / Math.max(cropW, cropH);
    return {
      backgroundSize: `${webW * scale}px ${webH * scale}px`,
      backgroundPosition: `${-cropX * scale}px ${-cropY * scale}px`,
    };
  })();

  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-2 flex-shrink-0 group"
      title={`Person ${cluster.cluster_id + 1} · ${cluster.face_count} photo${cluster.face_count !== 1 ? "s" : ""}`}
    >
      {/* Face circle */}
      <div
        className={`relative overflow-hidden rounded-full transition-all duration-200
          ${
            isActive
              ? "ring-2 ring-indigo-500 ring-offset-2 ring-offset-zinc-950 scale-110"
              : "ring-1 ring-zinc-700 group-hover:ring-zinc-500"
          }`}
        style={{ width: CIRCLE_SIZE, height: CIRCLE_SIZE }}
      >
        {blobUrl ? (
          <div
            style={{
              width: "100%",
              height: "100%",
              backgroundImage: `url(${blobUrl})`,
              backgroundRepeat: "no-repeat",
              backgroundSize: bgCrop?.backgroundSize ?? "cover",
              backgroundPosition: bgCrop?.backgroundPosition ?? "center",
            }}
          />
        ) : (
          <div className="w-full h-full bg-zinc-800 animate-pulse" />
        )}
      </div>

      {/* Count badge */}
      <span
        className={`text-xs tabular-nums transition-colors
        ${isActive ? "text-indigo-400 font-medium" : "text-zinc-500 group-hover:text-zinc-300"}`}
      >
        {cluster.face_count}
      </span>
    </button>
  );
}
