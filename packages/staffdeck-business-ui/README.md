# @staffdeck/business-ui

This package is the versioned source of the StaffDeck business surfaces that
are consumed by both StaffDeck and PilotDeck. It owns business interaction and
rendering while each host supplies an adapter for transport, auth context,
notifications, navigation, and localized labels.

The package exports the formal Knowledge, Skills, and Distill page implementations,
their generic host bridges, and the shared graph/version-detail renderers.
These are the original StaffDeck page flows with transport, auth, navigation,
notifications, and UI primitives supplied by the host adapter. PilotDeck
vendors the exact checked-in release under its composition module tree; it does
not import a StaffDeck checkout or maintain a second page implementation.
