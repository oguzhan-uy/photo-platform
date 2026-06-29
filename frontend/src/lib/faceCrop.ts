import type { CSSProperties } from 'react'
import type { Face, Photo } from '../types'

/**
 * Compute CSS properties to position an <img> inside a fixed-size square container
 * so that the detected face region fills the container, with some padding.
 *
 * The container must have `position: relative; overflow: hidden`.
 * Apply the returned style directly to the <img>.
 */
export function computeFaceCrop(
  photo: Photo,
  face: Face,
  containerSize: number,
): CSSProperties | null {
  if (
    face.bbox_x == null ||
    face.bbox_y == null ||
    face.bbox_w == null ||
    face.bbox_h == null ||
    !photo.width ||
    !photo.height
  ) {
    return null
  }

  // Add contextual padding (50% of face width on each side) so the crop looks natural.
  const pad = face.bbox_w * 0.5
  const cropX = Math.max(0, face.bbox_x - pad)
  const cropY = Math.max(0, face.bbox_y - pad)
  const cropW = Math.min(photo.width - cropX, face.bbox_w + 2 * pad)
  const cropH = Math.min(photo.height - cropY, face.bbox_h + 2 * pad)

  // Scale so the larger dimension fits the container.
  const scale = containerSize / Math.max(cropW, cropH)

  return {
    position: 'absolute',
    width:  `${photo.width  * scale}px`,
    height: `${photo.height * scale}px`,
    left:   `${-cropX * scale}px`,
    top:    `${-cropY * scale}px`,
  }
}
