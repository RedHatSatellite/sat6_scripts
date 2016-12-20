Name:           sat6_scripts
Version:        0.1
Release:        3%{?dist}
Summary:        Scripts to automate Satellite 6 tasks

License:        GPL
URL:            https://github.com/ggatward/sat6_scripts
Source0:        sat6_scripts-0.1.tar.gz

Requires:       python >= 2.7, PyYAML

%description
Various scripts to substantially automate management tasks of Satellite 6, including:
- content export/import in disconnected environments,
- content publish/promote activities


%prep
%autosetup


%build


%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/local/{bin,etc/sat6_scripts}
mkdir -p %{buildroot}/usr/share/{doc/sat6_scripts,sat6_scripts/config}
install -m 0644 README.md %{buildroot}/usr/share/doc/sat6_scripts/README.md
install -m 0644 LICENSE %{buildroot}/usr/share/doc/sat6_scripts/LICENSE
install -m 0644 docs/sat62_install.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62_install.txt
install -m 0644 docs/sat62disc_install.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62disc_install.txt
install -m 0644 docs/sat62_hardening.txt %{buildroot}/usr/share/doc/sat6_scripts/sat62_hardening.txt
install -m 0644 config/config.yml.example %{buildroot}/usr/share/sat6_scripts/config/config.yml
install -m 0644 config/exports.yml.example %{buildroot}/usr/share/sat6_scripts/config/exports.yml
install -m 0755 bin/check_sync %{buildroot}/usr/local/bin/check_sync
install -m 0755 bin/sat_export %{buildroot}/usr/local/bin/sat_export
install -m 0755 bin/sat_import %{buildroot}/usr/local/bin/sat_import
install -m 0755 bin/clean_content_views %{buildroot}/usr/local/bin/clean_content_views
install -m 0755 bin/publish_content_views %{buildroot}/usr/local/bin/publish_content_views
install -m 0755 bin/promote_content_views %{buildroot}/usr/local/bin/promote_content_views
install -m 0755 bin/download_manifest %{buildroot}/usr/local/bin/download_manifest
install -m 0644 helpers.py %{buildroot}/usr/share/sat6_scripts/helpers.py
install -m 0644 check_sync.py %{buildroot}/usr/share/sat6_scripts/check_sync.py
install -m 0644 sat_export.py %{buildroot}/usr/share/sat6_scripts/sat_export.py
install -m 0644 sat_import.py %{buildroot}/usr/share/sat6_scripts/sat_import.py
install -m 0644 publish_content_views.py %{buildroot}/usr/share/sat6_scripts/publish_content_views.py
install -m 0644 promote_content_views.py %{buildroot}/usr/share/sat6_scripts/promote_content_views.py
install -m 0644 clean_content_views.py %{buildroot}/usr/share/sat6_scripts/clean_content_views.py
install -m 0644 download_manifest.py %{buildroot}/usr/share/sat6_scripts/download_manifest.py



%files
%doc /usr/share/doc/sat6_scripts/README.md
%doc /usr/share/doc/sat6_scripts/sat62_install.txt
%doc /usr/share/doc/sat6_scripts/sat62disc_install.txt
%doc /usr/share/doc/sat6_scripts/sat62_hardening.txt
%license /usr/share/doc/sat6_scripts/LICENSE
%config(noreplace) /usr/share/sat6_scripts/config/config.yml
%config(noreplace) /usr/share/sat6_scripts/config/exports.yml

/usr/share/sat6_scripts/helpers.py
/usr/share/sat6_scripts/check_sync.py
/usr/share/sat6_scripts/sat_export.py
/usr/share/sat6_scripts/sat_import.py
/usr/share/sat6_scripts/publish_content_views.py
/usr/share/sat6_scripts/promote_content_views.py
/usr/share/sat6_scripts/clean_content_views.py
/usr/share/sat6_scripts/download_manifest.py

/usr/local/bin/check_sync
/usr/local/bin/sat_export
/usr/local/bin/sat_import
/usr/local/bin/clean_content_views
/usr/local/bin/publish_content_views
/usr/local/bin/promote_content_views
/usr/local/bin/download_manifest

%exclude /usr/share/sat6_scripts/*.pyc
%exclude /usr/share/sat6_scripts/*.pyo

%post
# Only run on initial install
if [ $1 -eq 1 ]; then
  ln -s /usr/share/sat6_scripts/config/config.yml /usr/local/etc/sat6_scripts/config.yml
  ln -s /usr/share/sat6_scripts/config/exports.yml /usr/local/etc/sat6_scripts/exports.yml
fi

%postun
# Only run on a complete uninstall
if [ $1 -eq 0 ]; then
  unlink /usr/local/etc/sat6_scripts/config.yml
  unlink /usr/local/etc/sat6_scripts/exports.yml
fi


%changelog

