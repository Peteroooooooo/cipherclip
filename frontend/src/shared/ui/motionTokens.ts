import type { Transition } from 'motion/react'

/** visionOS-style springs without overshoot, shared by every Motion animation in the app. */
export const SPRING_SMOOTH: Transition = { type: 'spring', visualDuration: 0.42, bounce: 0 }
export const SPRING_SNAPPY: Transition = { type: 'spring', visualDuration: 0.3, bounce: 0.12 }

/** The same smooth spring as a CSS `linear()` easing, for Web Animations API calls. */
export const SPRING_SMOOTH_EASING =
  'linear(0, 0.0014, 0.0053 1.02%, 0.0197 2.04%, 0.0455 3.22%, 0.084 4.58%, 0.166 6.96%, 0.3743 12.39%, ' +
  '0.4725 15.1%, 0.5714, 0.6564, 0.7277 24.27%, 0.7892 27.49%, 0.8405 30.88%, 0.8638, 0.8839 34.62%, ' +
  '0.9028 36.65%, 0.92, 0.9344 41.07%, 0.9471, 0.9575 45.82%, 0.9671 48.53%, 0.9817 54.64%, 0.9906 61.43%, ' +
  '0.9961 70.08%, 0.9988 81.45%, 0.9999 99.95%)'
