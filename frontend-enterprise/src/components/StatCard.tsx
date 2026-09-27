import * as Source from '@staffdeck/business-ui/FormalStatCard';
import { FormalPrimitives } from '../business-ui/formal-primitives';
import type { ComponentProps } from 'react';
export * from '@staffdeck/business-ui/FormalStatCard';
export function StatCard(props: ComponentProps<typeof Source.StatCard>) { return <FormalPrimitives><Source.StatCard {...props} /></FormalPrimitives>; }
