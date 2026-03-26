/**
 * Avatar Player Component
 *
 * Displays the LiveAvatar video stream using the LiveKit React SDK.
 * Connects to the LiveKit room and shows the avatar video track.
 */

import { useEffect, useState } from 'react'
import {
  LiveKitRoom,
  VideoTrack,
  RoomAudioRenderer,
  StartAudio,
  useRemoteParticipants,
  useTracks,
} from '@livekit/components-react'
import { Track } from 'livekit-client'

interface AvatarPlayerProps {
  livekitUrl: string
  livekitToken: string
  onConnectionChange?: (connected: boolean) => void
}

function AvatarVideoTrack() {
  const tracks = useTracks([Track.Source.Camera])

  const videoTrack = tracks.find(
    (t) => t.source === Track.Source.Camera && t.publication.track
  )

  if (!videoTrack) {
    return (
      <div className="flex items-center justify-center h-full text-white text-lg">
        <div className="text-center">
          <div className="animate-pulse mb-2">Verbinde mit Avatar...</div>
          <div className="text-sm text-gray-400">Warte auf Video-Stream</div>
        </div>
      </div>
    )
  }

  return (
    <VideoTrack
      trackRef={videoTrack}
      style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top center' }}
    />
  )
}

export default function AvatarPlayer({
  livekitUrl,
  livekitToken,
  onConnectionChange,
}: AvatarPlayerProps) {
  const [isConnected, setIsConnected] = useState(false)

  return (
    <div className="avatar-container bg-gray-900 rounded-xl overflow-hidden shadow-2xl">
      <LiveKitRoom
        serverUrl={livekitUrl}
        token={livekitToken}
        connect={true}
        audio={false}
        video={false}
        onConnected={() => {
          setIsConnected(true)
          onConnectionChange?.(true)
        }}
        onDisconnected={() => {
          setIsConnected(false)
          onConnectionChange?.(false)
        }}
        style={{ height: '100%' }}
      >
        <AvatarVideoTrack />
        {/* RoomAudioRenderer handles all remote audio tracks */}
        <RoomAudioRenderer />
        {/* StartAudio: required for iOS Safari/Chrome — triggers room.startAudio()
            on first user gesture to unlock WebRTC audio autoplay policy */}
        <StartAudio label="Audio aktivieren" />

        {/* Connection status indicator */}
        <div className="absolute top-3 right-3">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
            title={isConnected ? 'Verbunden' : 'Getrennt'}
          />
        </div>
      </LiveKitRoom>
    </div>
  )
}
