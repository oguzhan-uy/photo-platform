import { apiFetch } from './client'
import type { AccessResponse, Cluster, Face, Gallery, Photo, PhotoUrl, PublicGallery } from '../types'

export const getPublicGalleries = () =>
  apiFetch<PublicGallery[]>('/galleries')

export const accessGallery = (galleryId: string, passcode: string) =>
  apiFetch<AccessResponse>(`/access/${galleryId}`, {
    method: 'POST',
    body: JSON.stringify({ passcode }),
  })

export const getGallery = () => apiFetch<Gallery>('/me/gallery')

export const getPhotos = () => apiFetch<Photo[]>('/me/photos')

export const getPhotoUrl = (photoId: string) =>
  apiFetch<PhotoUrl>(`/me/photos/${photoId}/url`)

export const getClusters = () => apiFetch<Cluster[]>('/me/clusters')

export const getPhotosByCluster = (clusterId: number) =>
  apiFetch<Photo[]>(`/me/photos/by-cluster/${clusterId}`)

export const getPhotoFaces = (photoId: string) =>
  apiFetch<Face[]>(`/me/photos/${photoId}/faces`)
