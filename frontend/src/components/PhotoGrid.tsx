import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetchBlob } from "../api/client";
import type { Photo } from "../types";

function usePhotoBlob(photoId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["photo-blob", photoId],
    queryFn: () => apiFetchBlob(`/me/photos/${photoId}/data`),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

interface PhotoCardProps {
  photo: Photo;
  onClick: () => void;
}

function PhotoCard({ photo, onClick }: PhotoCardProps) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          obs.disconnect();
        }
      },
      { rootMargin: "400px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const { data: blobUrl } = usePhotoBlob(photo.id, isVisible);

  return (
    <div
      ref={ref}
      onClick={onClick}
      className="relative aspect-square overflow-hidden bg-zinc-800 cursor-pointer group"
    >
      {blobUrl ? (
        <>
          <img
            src={blobUrl}
            alt=""
            draggable={false}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/25 transition-colors duration-300 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-300 drop-shadow-lg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
              />
            </svg>
          </div>
        </>
      ) : (
        <div className="w-full h-full bg-zinc-800 animate-pulse" />
      )}
    </div>
  );
}

interface Props {
  photos: Photo[];
  onOpenLightbox: (index: number) => void;
  loading?: boolean;
}

export function PhotoGrid({ photos, onOpenLightbox, loading = false }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-0.5">
        {Array.from({ length: 18 }).map((_, i) => (
          <div key={i} className="aspect-square bg-zinc-800 animate-pulse" />
        ))}
      </div>
    );
  }

  if (photos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center px-4">
        <div className="w-16 h-16 bg-zinc-800 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-8 h-8 text-zinc-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
        </div>
        <p className="text-zinc-400 text-sm font-medium">No photos here yet</p>
        <p className="text-zinc-600 text-sm mt-1">
          Check back soon or clear the filter above.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-0.5">
      {photos.map((photo, index) => (
        <PhotoCard
          key={photo.id}
          photo={photo}
          onClick={() => onOpenLightbox(index)}
        />
      ))}
    </div>
  );
}
