                  <div className="grid grid-cols-1 gap-2.5">
                    {visibleFiles.map((file) => (
                      <FileCard
                        key={file.id}
                        file={file}
                        onPlay={(f) => {
                          // Root "My Cloud Files" rows are Seedr files too, but
                          // they must use the same resolver as the working folder
                          // view so Vercel + Render always targets the backend.
                          if (
                            f.ownerId === 'seedr' &&
                            (f.type === 'video' || f.type === 'audio')
                          ) {
                            void handleStreamSeedrFile({
                              id: f.id,
                              streamId: f.streamId || f.id,
                              name: f.name,
                              size: f.size,
                              folderId: '',
                              folderPath: f.folder || '/'
                            });
                            return;
                          }

                          setActiveMediaFile(f);
                          setIsPlayerMinimized(false);
                        }}
                        streamLoading={file.ownerId === 'seedr' && seedrStreamLoadingId === file.id}
                        onCopyDownloadLink={file.ownerId === 'seedr'
                          ? async (f) => {
                              const result = await api.getSeedrFileDownload(f.id);
                              const directUrl = String(result?.url || '').trim();
                              if (!directUrl) {
                                throw new Error('Seedr did not return a download URL.');
                              }
                              await navigator.clipboard.writeText(directUrl);
                            }
                          : undefined}
                        onRename={(f) => setRenameItem({ id: f.id, name: f.name, isFolder: false })}
                        onMove={(f) => setMoveFile(f)}
                        onSeedrDelete={file.ownerId === 'seedr'
                          ? (f) => {
                              const seedrFile = seedrAllPrefetchedFiles.find(item => item.id === f.id);
                              if (!seedrFile) {
                                setSeedrError('Seedr file is no longer available. Refresh the library and try again.');
                                return;
                              }
                              return handleDeleteSeedrFile(seedrFile);
                            }
                          : undefined}
                        canEdit={activeUser?.role !== 'viewer'}
                        canDelete={file.ownerId === 'seedr' ? true : activeUser?.role === 'admin'}
                      />
                    ))}
                  </div>
                )}

                {seedrPrefetchLoading && currentFolder === '/' && seedrAllPrefetchedFiles.length === 0 ? (
                  <div className="py-10 text-center rounded-2xl bg-slate-900 border border-slate-800 p-8">
                    <RefreshCw className="w-8 h-8 text-emerald-400 mx-auto mb-3 animate-spin" />
                    <h3 className="text-sm font-bold text-slate-300">Loading Seedr files…</h3>
                    <p className="text-xs text-slate-500 mt-1">Folder metadata is ready. Loading file details in the background.</p>
                  </div>