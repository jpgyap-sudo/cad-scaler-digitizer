class OrthographicProjector:
    def project(self, document, plane='top'):
        return {'plane':plane,'entities':len(document.entities)}
