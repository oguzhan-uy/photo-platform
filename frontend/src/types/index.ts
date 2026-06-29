export interface Photo {
  id: string
  gallery_id: string
  status: 'uploaded' | 'processing' | 'ready' | 'failed'
  width: number | null
  height: number | null
  created_at: string
}

export interface Gallery {
  id: string
  client_id: string
  title: string
  published: boolean
  expires_at: string | null
  created_at: string
}

export interface Cluster {
  cluster_id: number
  face_count: number
  representative_photo_id: string
}

export interface Face {
  id: string
  photo_id: string
  gallery_id: string
  bbox_x: number | null
  bbox_y: number | null
  bbox_w: number | null
  bbox_h: number | null
  det_score: number | null
  cluster_id: number | null
  created_at: string
}

export interface PhotoUrl {
  url: string
  expires_in: number
}

export interface AccessResponse {
  token: string
  gallery_id: string
  expires_in: number
}

export interface PublicGallery {
  id: string
  title: string
  has_cover: boolean
}

// Admin types
export interface ClientOut {
  id: string
  display_name: string
  contact: string | null
  consent_biometric: boolean
  created_at: string
}

export interface GalleryOut {
  id: string
  client_id: string
  title: string
  published: boolean
  expires_at: string | null
  cover_photo_id: string | null
  created_at: string
}

export interface PhotoOut {
  id: string
  gallery_id: string
  status: 'uploaded' | 'processing' | 'ready' | 'failed'
  width: number | null
  height: number | null
  created_at: string
}

export interface PhotoConfirmOut {
  photo_id: string
  status: string
  job_id: string
}

export interface DeletionLogOut {
  id: string
  event_type: string
  target_type: string
  target_id: string
  purged_photos: number
  purged_faces: number
  purged_r2_objects: number
  executed_by: string
  created_at: string
}
