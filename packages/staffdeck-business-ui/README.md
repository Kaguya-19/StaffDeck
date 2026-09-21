# @staffdeck/business-ui

This package is the versioned source of the StaffDeck business surfaces that
are consumed by both StaffDeck and PilotDeck. It owns business interaction and
rendering while each host supplies an adapter for transport, auth context,
notifications, navigation, and localized labels.

The package currently exports the Knowledge graph and lifecycle/structure
operations plus SOP draft management. The PilotDeck build vendors the exact
`0.1.0` release under its composition module tree; it does not import a
StaffDeck checkout or maintain a second implementation.

The package deliberately exposes public operation clients rather than either
host's private stores or routes. Enterprise and PilotDeck adapters therefore
remain independently buildable and independently deployable.
