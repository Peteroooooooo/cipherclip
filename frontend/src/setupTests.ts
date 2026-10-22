import '@testing-library/jest-dom/vitest'
import { MotionGlobalConfig } from 'motion/react'

// jsdom has no real animation frames; finish motion animations instantly so exit
// transitions do not keep removed elements in the DOM during assertions.
MotionGlobalConfig.skipAnimations = true
