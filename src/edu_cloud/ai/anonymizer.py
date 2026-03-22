class Anonymizer:
    def __init__(self):
        self._map: dict[str, str] = {}
        self._reverse: dict[str, str] = {}
        self._counter = 0

    def _get_id(self, name: str) -> str:
        if name not in self._map:
            self._counter += 1
            anon_id = f"S{self._counter:03d}"
            self._map[name] = anon_id
            self._reverse[anon_id] = name
        return self._map[name]

    def anonymize(self, text: str, names: list[str]) -> str:
        for name in sorted(names, key=len, reverse=True):
            anon_id = self._get_id(name)
            text = text.replace(name, anon_id)
        return text

    def anonymize_data(self, data, names: list[str]):
        if isinstance(data, str):
            return self.anonymize(data, names)
        if isinstance(data, dict):
            return {k: self.anonymize_data(v, names) for k, v in data.items()}
        if isinstance(data, list):
            return [self.anonymize_data(item, names) for item in data]
        return data

    def deanonymize(self, text: str) -> str:
        for anon_id, name in sorted(self._reverse.items(), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(anon_id, name)
        return text

    def reset(self):
        self._map.clear()
        self._reverse.clear()
        self._counter = 0
